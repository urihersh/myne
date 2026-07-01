/**
 * WhatsApp bot — Baileys-based.
 *
 * Responsibilities:
 *   - Maintain a WhatsApp connection (QR auth, auto-reconnect, schedule window)
 *   - Watch configured groups for images/videos
 *   - Send each media file to the Python backend for face recognition
 *   - Forward matched media to the configured recipient (or queue for daily digest)
 *   - Expose a small Express API for the Python backend to query status and send messages
 */

require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') });

process.on('uncaughtException', (err) => {
  console.error('[bot] Uncaught exception — process will exit:', err);
  process.exit(1);
});
process.on('unhandledRejection', (reason) => {
  console.error('[bot] Unhandled rejection — process will exit:', reason);
  process.exit(1);
});

// Baileys prints raw Signal session objects to stdout during message decryption.
// Filter them out so they don't pollute the logs.
const _origWrite = process.stdout.write.bind(process.stdout);
process.stdout.write = (chunk, ...args) => {
  if (typeof chunk === 'string' && chunk.includes('Closing session:')) return true;
  return _origWrite(chunk, ...args);
};

// Tee stdout/stderr to data/logs/bot.log so the web UI can read it.
(function setupFileLog() {
  const DATA_DIR_EARLY = process.env.DATA_DIR || require('path').join(__dirname, '..', 'data');
  const logsDir = require('path').join(DATA_DIR_EARLY, 'logs');
  try { require('fs').mkdirSync(logsDir, { recursive: true }); } catch (_) {}
  const logStream = require('fs').createWriteStream(
    require('path').join(logsDir, 'bot.log'), { flags: 'a' }
  );
  const _ow = process.stdout.write.bind(process.stdout);
  const _oe = process.stderr.write.bind(process.stderr);
  process.stdout.write = (chunk, enc, cb) => { logStream.write(chunk); return _ow(chunk, enc, cb); };
  process.stderr.write = (chunk, enc, cb) => { logStream.write(chunk); return _oe(chunk, enc, cb); };
})();

const {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  downloadMediaMessage,
  fetchLatestBaileysVersion,
} = require('@whiskeysockets/baileys');
const express = require('express');
const axios = require('axios');
const QRCode = require('qrcode');
const FormData = require('form-data');
const path = require('path');
const fs = require('fs');
const pino = require('pino');

const BOT_PORT = parseInt(process.env.BOT_PORT || '3001');
const PYTHON_API_URL = process.env.PYTHON_API_URL || 'http://localhost:8000';
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, '..', 'data');
const SESSION_DIR = path.join(DATA_DIR, 'whatsapp-session');

fs.mkdirSync(SESSION_DIR, { recursive: true });

function buildCaption(names, count, isVideo, confidence, groupName, lang) {
  const conf = (confidence * 100).toFixed(0);
  if (lang === 'he') {
    const medium = isVideo ? 'סרטון' : 'תמונה';
    const verb = count > 1 ? 'מופיעים' : 'מופיע';
    return `${names} ${verb} ב${medium}! (${conf}% ביטחון) — מ"${groupName}"`;
  }
  const medium = isVideo ? 'video' : 'photo';
  const verb = count > 1 ? 'are' : 'is';
  return `${names} ${verb} in this ${medium}! (${conf}% confidence) — from "${groupName}"`;
}

// Limits concurrent face-recognition calls to the backend so an image burst
// from one group doesn't overwhelm the CPU-heavy analysis on slow machines.
class Semaphore {
  constructor(n) { this._n = n; this._waiting = []; }
  async acquire() {
    if (this._n > 0) { this._n--; return; }
    await new Promise(r => this._waiting.push(r));
  }
  release() {
    if (this._waiting.length > 0) this._waiting.shift()();
    else this._n++;
  }
}
const analysisSem = new Semaphore(2);

// --- Connection state ---
let currentQR = null;
let isConnected = false;

async function waitForConnection(timeoutMs = 20000) {
  if (isConnected) return true;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await new Promise(r => setTimeout(r, 1000));
    if (isConnected) return true;
  }
  return false;
}

async function sendWithRetry(fn, retries = 3, delayMs = 4000) {
  for (let attempt = 1; attempt <= retries; attempt++) {
    if (!await waitForConnection(20000)) throw new Error('Not connected after 20s');
    try {
      return await fn();
    } catch (e) {
      if (attempt === retries) throw e;
      console.warn(`[bot] Send failed (attempt ${attempt}/${retries}): ${e.message} — retrying in ${delayMs}ms`);
      await new Promise(r => setTimeout(r, delayMs));
    }
  }
}
let manuallyDisconnected = false;
let presenceInterval = null;
let phoneInfo = null;
let allGroups = [];
let sock = null;

// --- Settings cache (30s TTL avoids a DB round-trip on every incoming message) ---
let _cachedSettings = null;
let _settingsCacheTs = 0;
const SETTINGS_TTL_MS = 30_000;

async function getSettings() {
  const now = Date.now();
  if (_cachedSettings && now - _settingsCacheTs < SETTINGS_TTL_MS) return _cachedSettings;
  const res = await axios.get(`${PYTHON_API_URL}/api/settings`, { timeout: 5000 });
  _cachedSettings = res.data;
  _settingsCacheTs = now;
  return _cachedSettings;
}

// --- Message stats ---
// groupId → [{ts, fromMe}] — in-memory, resets on bot restart
const statLog = new Map();

// Simple today-media counter (images + videos received); resets at midnight
let todayMediaCount = 0;
let todayMediaDate = new Date().toDateString();

function tickMediaCounter() {
  const today = new Date().toDateString();
  if (today !== todayMediaDate) { todayMediaCount = 0; todayMediaDate = today; }
  todayMediaCount++;
}

function storeStatEntry(msg) {
  const jid = msg.key?.remoteJid;
  if (!jid) return;
  if (!statLog.has(jid)) statLog.set(jid, []);
  statLog.get(jid).push({ ts: (msg.messageTimestamp || 0) * 1000, fromMe: !!msg.key.fromMe });
}

// --- Message type helpers ---

function isImageMsg(msg) {
  const msgType = Object.keys(msg.message || {})[0];
  return msgType === 'imageMessage' ||
    (msgType === 'documentMessage' && (msg.message?.documentMessage?.mimetype || '').startsWith('image/'));
}

function isVideoMsg(msg) {
  const msgType = Object.keys(msg.message || {})[0];
  return msgType === 'videoMessage' ||
    (msgType === 'documentMessage' && (msg.message?.documentMessage?.mimetype || '').startsWith('video/'));
}

function getSender(msg) {
  const jid = msg.key.participant || msg.key.remoteJid || '';
  const [localPart] = jid.split('@');
  return msg.pushName || localPart;
}

// --- WhatsApp connection ---

async function connect() {
  const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    auth: state,
    logger: pino({ level: 'silent' }),
    printQRInTerminal: false,
    browser: ['Myne', 'Chrome', '1.0'],
    markOnlineOnConnect: false,
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      currentQR = qr;
      isConnected = false;
      console.log('[bot] QR code ready — open the Settings page to scan.');
    }

    if (connection === 'open') {
      isConnected = true;
      currentQR = null;
      const me = sock.user;
      const number = me.id.split(':')[0];
      phoneInfo = { number, name: me.name || `+${number}` };
      console.log(`[bot] Connected as ${phoneInfo.name} (+${phoneInfo.number})`);
      // Stay unavailable so WhatsApp doesn't suppress phone notifications
      await sock.sendPresenceUpdate('unavailable');
      if (presenceInterval) clearInterval(presenceInterval);
      presenceInterval = setInterval(async () => {
        if (isConnected) await sock.sendPresenceUpdate('unavailable').catch(() => {});
      }, 5 * 60 * 1000);
      await refreshGroupsAndChats();
    }

    if (connection === 'close') {
      isConnected = false;
      phoneInfo = null;
      if (presenceInterval) { clearInterval(presenceInterval); presenceInterval = null; }
      const code = lastDisconnect?.error?.output?.statusCode;
      if (manuallyDisconnected) {
        console.log('[bot] Disconnected manually — not reconnecting.');
        return;
      }
      const shouldReconnect = code !== DisconnectReason.loggedOut;
      // 440 = conflict: another session connected. Reconnecting immediately creates a
      // feedback loop where each reconnect kicks out the other, causing endless 440s.
      // Wait 30s to let the competing session stabilise before retrying.
      const reconnectDelay = code === 440 ? 30000 : 5000;
      console.log(`[bot] Disconnected (code ${code}). Reconnect: ${shouldReconnect}`);
      if (shouldReconnect) {
        setTimeout(connect, reconnectDelay);
      } else {
        // Logged out — clear session so QR is shown on next start
        fs.rmSync(SESSION_DIR, { recursive: true, force: true });
        fs.mkdirSync(SESSION_DIR, { recursive: true });
        setTimeout(connect, 3000);
      }
    }
  });

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    // 'notify' = new live message; 'append' = history sync from device
    const isHistory = type === 'append';

    for (const msg of messages) {
      storeStatEntry(msg);
      if (msg.key.fromMe) continue;

      const isImage = isImageMsg(msg);
      const isVideo = isVideoMsg(msg);

      if (isImage || isVideo) tickMediaCounter();
      if (!isImage && !isVideo) continue;

      // For history-sync messages, only process media from the last 24h to avoid
      // re-processing the full Baileys initial sync on every bot restart
      if (isHistory) {
        const msgAgeMs = Date.now() - (msg.messageTimestamp || 0) * 1000;
        if (msgAgeMs > 24 * 60 * 60 * 1000) continue;
        console.log(`[bot] History-sync ${isVideo ? 'video' : 'image'} from ${new Date((msg.messageTimestamp || 0) * 1000).toISOString()}`);
      }

      const groupId = msg.key.remoteJid;
      if (!groupId?.endsWith('@g.us')) continue;

      let settings;
      try {
        settings = await getSettings();
      } catch (e) {
        console.error('[bot] Could not fetch settings:', e.message);
        continue;
      }

      let watchGroups = [];
      try { watchGroups = JSON.parse(settings.watch_groups || '[]'); } catch (_) {}
      const groupConfig = watchGroups.find(g => g.id === groupId);
      const scanAll = settings.scan_all_groups === 'true';
      if (!groupConfig && !scanAll) continue;

      const forwardToId = settings.forward_to_id;
      const groupName = groupConfig?.name || allGroups.find(g => g.id === groupId)?.name || groupId;

      const delayMs = 3000 + Math.random() * 7000;
      await new Promise(r => setTimeout(r, delayMs));

      console.log(`[bot] ${isVideo ? 'Video' : 'Image'} from "${groupName}", downloading...`);

      let buffer;
      try {
        const downloadTimeout = new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Download timed out after 60s')), 60000)
        );
        buffer = await Promise.race([downloadMediaMessage(msg, 'buffer', {}), downloadTimeout]);
      } catch (e) {
        console.error('[bot] Failed to download media:', e.message);
        continue;
      }

      const senderName = getSender(msg);

      try {
        const form = new FormData();
        if (isVideo) {
          form.append('file', buffer, { filename: 'video.mp4', contentType: 'video/mp4' });
        } else {
          form.append('file', buffer, { filename: 'photo.jpg', contentType: 'image/jpeg' });
        }

        const endpoint = isVideo ? 'analyze-video' : 'analyze';
        const timeout = isVideo ? 600000 : 90000;
        await analysisSem.acquire();
        const res = await axios.post(
          `${PYTHON_API_URL}/api/${endpoint}?group_id=${encodeURIComponent(groupId)}&group_name=${encodeURIComponent(groupName)}&sender=${encodeURIComponent(senderName)}`,
          form,
          { headers: { ...form.getHeaders() }, timeout }
        ).finally(() => analysisSem.release());

        const result = res.data;
        const matchedKids = (result.matches || []).filter(m => m.matched);
        const extra = isVideo ? ` frames_sampled=${result.frames_sampled}` : '';
        console.log(`[bot] matched=${result.matched}, faces=${result.faces_detected}${extra}, kids=${matchedKids.map(m => m.kid_name || m.kid_id).join(', ') || 'none'}, saved_to_folder=${result.saved_to_folder}, saved_to_gp=${result.saved_to_gp}`);

        if (result.matched) {
          const names = matchedKids.map(m => m.kid_name || 'your kid').join(' & ');
          const bestConf = Math.max(...matchedKids.map(m => m.confidence));
          const lang = settings.language || 'en';
          const caption = buildCaption(names, matchedKids.length, isVideo, bestConf, groupName, lang);

          if (settings.digest_mode === 'true') {
            const digestForm = new FormData();
            if (isVideo) {
              digestForm.append('file', buffer, { filename: 'video.mp4', contentType: 'video/mp4' });
            } else {
              digestForm.append('file', buffer, { filename: 'photo.jpg', contentType: 'image/jpeg' });
            }
            const params = new URLSearchParams({ sender: senderName, group_name: groupName, kid_names: names, is_video: String(isVideo) });
            await axios.post(`${PYTHON_API_URL}/api/digest/enqueue?${params}`, digestForm, { headers: digestForm.getHeaders() });
            console.log(`[bot] Queued for digest: ${names}`);
          } else if (forwardToId) {
            const msgContent = isVideo
              ? { video: buffer, caption }
              : { image: buffer, caption };
            const sent = await sendWithRetry(() => sock.sendMessage(forwardToId, msgContent));
            try {
              await sock.chatModify({ markRead: false, lastMessages: [sent] }, forwardToId);
            } catch (_) {}
            console.log(`[bot] Forwarded to ${forwardToId}`);
          }
        }
      } catch (e) {
        console.error('[bot] Analysis/forward failed:', e.message);
        // Save failed media so user can manually retry later
        try {
          const failedDir = path.join(DATA_DIR, 'failed');
          fs.mkdirSync(failedDir, { recursive: true });
          const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
          const ext = isVideo ? '.mp4' : '.jpg';
          const filename = `${timestamp}_${groupName.replace(/[^a-zA-Z0-9א-ת]/g, '_')}${ext}`;
          fs.writeFileSync(path.join(failedDir, filename), buffer);
          console.log(`[bot] Saved failed media to data/failed/${filename} for manual retry`);
        } catch (saveErr) {
          console.error('[bot] Could not save failed media:', saveErr.message);
        }
      }
    }
  });
}

async function refreshGroupsAndChats() {
  try {
    const chats = await sock.groupFetchAllParticipating();
    allGroups = Object.values(chats).map(g => ({ id: g.id, name: g.subject }));
    console.log(`[bot] Loaded ${allGroups.length} groups`);
  } catch (e) {
    console.error('[bot] Failed to load groups:', e.message);
  }
}

// --- Express API ---

const app = express();
app.use(express.json({ limit: '20mb' }));

app.get('/status', (req, res) => {
  const sessionExists = fs.readdirSync(SESSION_DIR).some(f => f.endsWith('.json'));
  res.json({ connected: isConnected, phone: phoneInfo, sessionExists });
});

app.get('/qr', async (req, res) => {
  if (!currentQR) return res.json({ qr: null });
  try {
    res.json({ qr: await QRCode.toDataURL(currentQR) });
  } catch (e) {
    res.json({ qr: null, error: e.message });
  }
});

app.post('/send', express.json({ limit: '20mb' }), async (req, res) => {
  if (!isConnected) return res.status(503).json({ error: 'Not connected' });
  const { to, caption, image_b64 } = req.body;
  if (!image_b64 || !to) return res.status(400).json({ error: 'Missing to or image_b64' });
  try {
    await sock.sendMessage(to, { image: Buffer.from(image_b64, 'base64'), caption: caption || '' });
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post('/send-video', express.json({ limit: '200mb' }), async (req, res) => {
  if (!isConnected) return res.status(503).json({ error: 'Not connected' });
  const { to, caption, video_b64 } = req.body;
  if (!video_b64 || !to) return res.status(400).json({ error: 'Missing to or video_b64' });
  try {
    await sock.sendMessage(to, { video: Buffer.from(video_b64, 'base64'), caption: caption || '' });
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post('/send-text', async (req, res) => {
  if (!isConnected) return res.status(503).json({ error: 'Not connected' });
  const { to, text } = req.body;
  if (!text || !to) return res.status(400).json({ error: 'Missing to or text' });
  try {
    await sock.sendMessage(to, { text });
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/message-stats', (req, res) => {
  const todayStart = new Date(); todayStart.setHours(0, 0, 0, 0);
  const todayTs = todayStart.getTime();
  const weekTs = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const last24Ts = Date.now() - 24 * 60 * 60 * 1000;

  let todayReceived = 0, todaySent = 0;
  const groupMap = {};
  const hourly = new Array(24).fill(0);

  for (const [groupId, entries] of statLog) {
    const group = allGroups.find(g => g.id === groupId);
    let todayCount = 0, weekCount = 0;
    for (const e of entries) {
      if (e.ts >= todayTs) {
        if (e.fromMe) todaySent++; else todayReceived++;
        todayCount++;
      }
      if (e.ts >= last24Ts) {
        // slot 0 = oldest hour, slot 23 = most recent hour
        const slotIndex = 23 - Math.floor((Date.now() - e.ts) / (60 * 60 * 1000));
        if (slotIndex >= 0 && slotIndex < 24) hourly[slotIndex]++;
      }
      if (e.ts >= weekTs) weekCount++;
    }
    if (weekCount > 0 && groupId.endsWith('@g.us')) {
      groupMap[groupId] = { id: groupId, name: group?.name || groupId, today: todayCount, week: weekCount };
    }
  }

  // Sync media counter date before reading
  const today = new Date().toDateString();
  if (today !== todayMediaDate) { todayMediaCount = 0; todayMediaDate = today; }

  const groups = Object.values(groupMap).sort((a, b) => b.today - a.today || b.week - a.week).slice(0, 15);
  res.json({
    today: { received: todayReceived, sent: todaySent, media: todayMediaCount },
    groups,
    hourly,
    total_groups: allGroups.length,
    active_today: groups.filter(g => g.today > 0).length,
  });
});

app.get('/groups', async (req, res) => {
  if (isConnected && (allGroups.length === 0 || req.query.refresh)) await refreshGroupsAndChats();
  res.json({ groups: allGroups });
});

app.get('/chats', async (req, res) => {
  if (isConnected && (allGroups.length === 0 || req.query.refresh)) await refreshGroupsAndChats();
  res.json({ chats: allGroups.map(g => ({ ...g, isGroup: true })) });
});

app.post('/wa-disconnect', async (req, res) => {
  if (!isConnected) return res.json({ ok: true, message: 'Already disconnected' });
  try {
    manuallyDisconnected = true;
    await sock.end();
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post('/wa-logout', async (req, res) => {
  try {
    manuallyDisconnected = false;
    if (isConnected) {
      await sock.logout();
    } else {
      fs.rmSync(SESSION_DIR, { recursive: true, force: true });
      fs.mkdirSync(SESSION_DIR, { recursive: true });
      connect().catch(err => console.error('[bot] Reconnect after logout error:', err));
    }
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post('/wa-connect', async (req, res) => {
  if (isConnected) return res.json({ ok: true, message: 'Already connected' });
  try {
    manuallyDisconnected = false;
    connect().catch(err => console.error('[bot] Reconnect error:', err));
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// --- Prune statLog entries older than 7 days to prevent unbounded growth ---
setInterval(() => {
  const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
  for (const [groupId, entries] of statLog) {
    const pruned = entries.filter(e => e.ts >= cutoff);
    if (pruned.length === 0) statLog.delete(groupId);
    else statLog.set(groupId, pruned);
  }
}, 60 * 60 * 1000);

// --- Schedule checker: connect/disconnect based on configured active hours ---
setInterval(async () => {
  try {
    const settings = await getSettings();
    if (settings.schedule_enabled !== 'true') return;
    const from = settings.schedule_from; // "HH:MM"
    const to = settings.schedule_to;     // "HH:MM"
    if (!from || !to) return;
    const now = new Date();
    const cur = now.getHours() * 60 + now.getMinutes();
    const [fh, fm] = from.split(':').map(Number);
    const [th, tm] = to.split(':').map(Number);
    const start = fh * 60 + fm;
    const end = th * 60 + tm;
    const inWindow = start <= end ? (cur >= start && cur < end) : (cur >= start || cur < end);
    if (inWindow && !isConnected && !manuallyDisconnected) {
      console.log('[schedule] Within active hours — connecting');
      manuallyDisconnected = false;
      connect().catch(err => console.error('[schedule] Connect error:', err));
    } else if (!inWindow && isConnected) {
      console.log('[schedule] Outside active hours — disconnecting');
      manuallyDisconnected = true;
      await sock.end();
    }
  } catch (_) {}
}, 60000);

app.listen(BOT_PORT, () => console.log(`[bot] API listening on http://localhost:${BOT_PORT}`));

console.log('[bot] Starting...');
connect().catch(err => console.error('[bot] Fatal:', err));
