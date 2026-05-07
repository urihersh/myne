const TRANSLATIONS = {
  en: {
    // Nav
    settings: 'Settings',
    // Tabs
    tab_activity: 'Activity',
    tab_kids: 'Kids',
    tab_groups: 'Groups',
    // Stats
    matched_today: 'matched today',
    scanned_today: 'scanned today',
    match_rate: 'match rate',
    // Digest
    photos_queued: 'photos queued',
    send_now: 'Send now',
    // Activity log
    recent_activity: 'Recent Activity',
    auto_refreshes: 'auto-refreshes',
    clear: 'Clear',
    all_results: 'All results',
    matches_only: 'Matches only',
    no_match_only: 'No-match only',
    filter_by_group: 'Filter by group…',
    filter_by_kid: 'Filter by kid…',
    reset: 'Reset',
    // Table headers
    col_time: 'Time',
    col_sender: 'Sender',
    col_group: 'Group',
    col_faces: 'Faces',
    col_result: 'Result',
    col_conf: 'Conf.',
    loading: 'Loading…',
    no_activity: 'No activity yet. Waiting for photos from monitored groups…',
    // Badges
    badge_match: 'Match',
    badge_no_match: 'No match',
    badge_manual: 'Matched manually',
    // Row actions
    send: 'Send',
    resend: 'Resend',
    // Test recognition
    test_recognition: 'Test Recognition',
    test_subtitle: 'Try photos or videos without needing WhatsApp',
    search_for_kid: 'Search for kid',
    all_kids: 'All kids',
    drop_photos_videos: 'Drop photos or videos, or click to select',
    files_selected: 'files selected',
    perform_actions_if_matched: 'Perform actions if matched',
    forward_if_matched: 'Forward if matched',
    run_test: 'Run',
    analyze: 'Analyze',
    result: 'Result',
    run_test_to_see: 'Run a test to see results here',
    no_faces_detected: 'No faces detected',
    match_found: '✓ Match!',
    no_match: 'No match',
    forwarded_badge: '✓ Forwarded',
    select_file_first: 'Select at least one photo or video.',
    no_kids_enrolled: 'No kids enrolled yet.',
    test_failed: 'Test failed — is the backend running?',
    // Kids tab
    enrolled_kids: 'Enrolled Kids',
    kids_subtitle: 'Upload clear face photos for each kid',
    delete_kid: 'Delete Kid',
    drop_photos: 'Drop photos here or click to upload',
    photo_hint: 'JPG, PNG, WEBP — multiple files OK',
    photo_tip: '💡 One clear face per photo, good lighting',
    confirm_faces: 'Confirm Faces',
    enroll_all: 'Enroll All',
    enrolled_photos: 'Enrolled Photos',
    delete_originals: 'Delete all originals',
    no_photos_enrolled: 'No photos enrolled yet.',
    // Add kid modal
    add_a_kid: 'Add a Kid',
    kid_name_placeholder: 'e.g. Emma',
    add: 'Add',
    cancel: 'Cancel',
    // Groups tab
    monitored_groups: 'Monitored Groups',
    groups_subtitle: 'Search and toggle groups to monitor',
    save: 'Save',
    search_groups: 'Search groups…',
    connect_wa_first: 'Connect WhatsApp in Settings to load groups.',
    // Configure tab
    match_confidence: 'Match Confidence',
    confidence_hint: 'Higher = fewer false positives. Lower = catches more but may include other kids.',
    more_matches: 'More matches',
    fewer_false: 'Fewer false positives',
    whatsapp_forward: 'WhatsApp Forward',
    enabled: 'Enabled',
    forward_description: 'Forward matched photos to a chat (e.g. your private chat with your spouse).',
    select_chat: '-- Select a chat --',
    save_to_folder: 'Save to Folder',
    save_folder_description: 'Save every matched photo to a local folder.',
    browse: 'Browse…',
    organise_by: 'Organise by',
    by_group: 'Group',
    by_kid: 'Kid',
    daily_digest: 'Daily Digest',
    digest_description: 'Instead of a ping per photo, get one daily summary.',
    send_at: 'Send at',
    activity_thumbnails: 'Activity Thumbnails',
    thumbnails_description: 'Save small thumbnails of matched photos in the activity log. Automatically deleted after a set time.',
    keep_for: 'Keep for',
    hours: 'hours',
    google_photos: 'Google Photos',
    gp_description: 'Upload every matched photo to Google Photos.',
    organise_albums: 'Organise albums by',
    no_album: 'No album',
    single_album: 'Single album',
    album_name: 'Album name',
    save_settings: 'Save Settings',
    // Backup
    backup_restore: 'Backup & Restore',
    backup_description: 'Backup includes all settings and enrolled kids (photos + face data). WhatsApp session is excluded.',
    export_backup: 'Export backup',
    restore_backup: 'Restore backup',
    // Settings page
    whatsapp_connection: 'WhatsApp Connection',
    wa_connected: 'Connected',
    wa_not_connected: 'Not connected.',
    disconnect: 'Disconnect',
    sign_out: 'Sign out',
    connect: 'Connect',
    waiting_qr: 'Waiting for QR code…',
    scan_qr_instruction: 'Open WhatsApp on your phone → Linked Devices → Link a Device',
    active_hours: 'Active hours',
    active_hours_subtitle: 'Auto-disconnect outside these hours so your phone gets notifications',
    from: 'From',
    to: 'To',
    bot_disconnects: 'Bot disconnects outside this window',
    integrations: 'Integrations',
    integrations_subtitle: 'Connect external services. Once configured here, each feature can be enabled per-app.',
    gp_not_connected_badge: 'Not connected',
    gp_connected_badge: 'Connected',
    how_to_credentials: 'How to get credentials ▸',
    gp_step_1: 'Go to <a href="https://console.cloud.google.com" target="_blank" class="text-blue-600 underline hover:text-blue-800">console.cloud.google.com</a>, create a project (or select one).',
    gp_step_2: 'Go to <strong>APIs &amp; Services → Library</strong>, search for <strong>Photos Library API</strong> and enable it.',
    gp_step_3: 'Go to <strong>APIs &amp; Services → OAuth consent screen</strong>.<br>Under <strong>Audience</strong>, set User Type to <strong>External</strong> and publishing status to <strong>In production</strong>.',
    gp_step_4: 'Go to <strong>APIs &amp; Services → Credentials → Create Credentials → OAuth Client ID</strong>.<br>Application type: <strong>Web application</strong>.',
    gp_step_5: 'Under <strong>Authorized redirect URIs</strong>, add exactly:<br><code class="bg-white border border-gray-200 px-1 rounded break-all select-all">http://localhost:8000/api/settings/google-photos/callback</code>',
    gp_step_6: 'Copy the <strong>Client ID</strong> and <strong>Client Secret</strong> into the fields below and click <strong>Save Settings</strong>, then click <strong>Connect with Google</strong>.',
    client_id: 'Client ID',
    client_secret: 'Client Secret',
    connect_google: 'Connect with Google',
    security: 'Security',
    security_subtitle: 'Lock the UI with a PIN to prevent unauthorised access on your network.',
    pin_lock: 'PIN lock',
    pin_digits: 'PIN (4–6 digits)',
    pin_keep_hint: 'Leave blank to keep current PIN.',
    // Tabs (new)
    tab_actions: 'Actions',
    tab_settings: 'Settings',
    // Language
    language: 'Language',
    // Dynamic subtitles
    nav_disconnected: 'Disconnected',
    kids_subtitle_1: '1 kid · {photos} photos enrolled',
    kids_subtitle_n: '{n} kids · {photos} photos enrolled',
    kid_photos_1: '1 photo enrolled',
    kid_photos_n: '{n} photos enrolled',
    groups_subtitle_0: 'No groups monitored · search to add',
    groups_subtitle_1: '1 group monitored · search to add or remove',
    groups_subtitle_n: '{n} groups monitored · search to add or remove',
    // WA status detail
    wa_session_disconnected: 'Disconnected — your phone is receiving notifications. Click Connect to resume.',
    wa_not_linked: 'Not linked. Scan the QR code below to connect.',
    // Test panel
    analyzing: 'Analyzing…',
    no_faces_in_frame: 'No faces in any sampled frame',
    try_clearer_photo: 'Try a clearer photo',
    nothing_sent: '(nothing would be sent)',
    no_kids_enrolled_yet: 'No kids enrolled yet',
    // Kid actions
    renamed: 'Renamed',
    rename_failed: 'Failed to rename',
    photo_enrolled: 'Photo enrolled!',
    // Kids grid / card
    add_kid: 'Add Kid',
    face_count_1: '1 face',
    face_count_n: '⚠ {n} faces',
    quality_too_small: 'Too small',
    quality_small: 'Small',
    quality_good: 'Good',
    enroll_btn: 'Enroll',
    discard_btn: 'Discard',
    del_orig_btn: 'Del. orig',
    remove_btn: 'Remove',
    deleted_state: 'Deleted',
    original_deleted: 'Original deleted — embedding kept',
    already_deleted: 'Already deleted',
    originals_deleted_1: '1 original deleted',
    originals_deleted_n: '{n} originals deleted',
    removed: 'Removed',
    failed_remove: 'Failed to remove',
    enrollment_failed: 'Enrollment failed',
    no_face_detected: 'No face detected',
    upload_failed: 'Upload failed',
    failed_add_kid: 'Failed to add kid',
    failed_delete: 'Failed to delete',
    kid_deleted: '{name} deleted',
    delete_kid_confirm: 'Delete {name} and all their enrolled photos?',
    delete_all_originals_confirm: 'Delete all original photos for {name}? Embeddings are kept.',
    rename_tooltip: 'Rename',
    // Groups
    scan_all_groups: 'Scan all groups for all kids',
    scan_all_groups_hint: 'When enabled, every group the bot is in will be scanned — not just the monitored ones below.',
    no_groups_match: 'No groups match your search.',
    search_to_add_groups: 'Search to add groups to monitor.',
    kids_count_1: '1 kid',
    kids_count_n: '{n} kids',
    groups_saved: 'Groups saved!',
    failed_save: 'Failed to save',
    refresh_from_wa: 'Refresh from WhatsApp',
    refresh_tooltip: 'Refresh',
    // Actions / settings toasts
    enter_folder_path: 'Enter a folder path to save photos',
    settings_saved: 'Settings saved!',
    failed_save_settings: 'Failed to save settings',
    folder_picker_unavailable: 'Folder picker unavailable — type the path manually',
    could_not_open_picker: 'Could not open folder picker',
    // Digest banner
    send_now: 'Send now',
    digest_on_prefix: 'Digest mode on ·',
    photos_queued: 'photos queued',
    // Activity
    clear_activity_confirm: 'Clear all activity logs?',
    // WA actions
    disconnecting: 'Disconnecting…',
    disconnected_phone_notif: 'Disconnected — your phone will now receive notifications',
    could_not_disconnect: 'Could not disconnect',
    signing_out: 'Signing out…',
    signed_out_qr: 'Signed out — scan QR to reconnect',
    could_not_sign_out: 'Could not sign out',
    connecting_ellipsis: 'Connecting…',
    reconnecting: 'Reconnecting…',
    could_not_connect: 'Could not connect',
    wa_logout_confirm: 'This will unlink the bot from your WhatsApp account. You will need to scan a QR code to reconnect. Continue?',
    // Model loading banner
    model_loading: 'First-time setup: downloading the face recognition model (~500 MB). This won\'t happen again.',
    model_error: 'Failed to load face recognition model.',
  },
  he: {
    // Nav
    settings: 'הגדרות',
    // Tabs
    tab_activity: 'פעילות',
    tab_kids: 'ילדים',
    tab_groups: 'קבוצות',
    // Stats
    matched_today: 'זוהו היום',
    scanned_today: 'נסרקו היום',
    match_rate: 'אחוז זיהוי',
    // Digest
    photos_queued: 'תמונות בהמתנה',
    send_now: 'שלח עכשיו',
    // Activity log
    recent_activity: 'פעילות אחרונה',
    auto_refreshes: 'מתרענן אוטומטית',
    clear: 'נקה',
    all_results: 'כל התוצאות',
    matches_only: 'זיהויים בלבד',
    no_match_only: 'ללא זיהוי',
    filter_by_group: '…סינון לפי קבוצה',
    filter_by_kid: '…סינון לפי ילד',
    reset: 'איפוס',
    // Table headers
    col_time: 'שעה',
    col_sender: 'שולח',
    col_group: 'קבוצה',
    col_faces: 'פנים',
    col_result: 'תוצאה',
    col_conf: 'ביטחון',
    loading: 'טוען…',
    no_activity: 'אין פעילות עדיין. ממתין לתמונות מקבוצות מנוטרות…',
    // Badges
    badge_match: 'זוהה',
    badge_no_match: 'לא זוהה',
    badge_manual: 'זוהה ידנית',
    // Row actions
    send: 'שלח',
    resend: 'שלח שוב',
    // Test recognition
    test_recognition: 'בדיקת זיהוי',
    test_subtitle: 'נסה תמונות או סרטונים ללא WhatsApp',
    search_for_kid: 'חפש ילד',
    all_kids: 'כל הילדים',
    drop_photos_videos: 'גרור תמונות או סרטונים, או לחץ לבחירה',
    files_selected: 'קבצים נבחרו',
    perform_actions_if_matched: 'בצע פעולות במידה וזוהה',
    forward_if_matched: 'העבר אם זוהה',
    run_test: 'הפעל',
    analyze: 'נתח',
    result: 'תוצאה',
    run_test_to_see: 'הפעל בדיקה לראות תוצאות',
    no_faces_detected: 'לא זוהו פנים',
    match_found: '✓ זוהה!',
    no_match: 'ללא התאמה',
    forwarded_badge: '✓ הועבר',
    select_file_first: 'בחר לפחות תמונה או סרטון אחד.',
    no_kids_enrolled: 'אין ילדים רשומים עדיין.',
    test_failed: 'הבדיקה נכשלה — האם השרת פועל?',
    // Kids tab
    enrolled_kids: 'ילדים רשומים',
    kids_subtitle: 'העלה תמונות פנים ברורות לכל ילד',
    delete_kid: 'מחק ילד',
    drop_photos: 'גרור תמונות לכאן או לחץ להעלאה',
    photo_hint: 'JPG, PNG, WEBP — ניתן מספר קבצים',
    photo_tip: '💡 פנים אחת ברורה לתמונה, תאורה טובה',
    confirm_faces: 'אשר פנים',
    enroll_all: 'רשום הכל',
    enrolled_photos: 'תמונות רשומות',
    delete_originals: 'מחק את כל המקוריות',
    no_photos_enrolled: 'אין תמונות רשומות עדיין.',
    // Add kid modal
    add_a_kid: 'הוסף ילד',
    kid_name_placeholder: 'לדוגמה: עמי',
    add: 'הוסף',
    cancel: 'ביטול',
    // Groups tab
    monitored_groups: 'קבוצות מנוטרות',
    groups_subtitle: 'חפש והפעל קבוצות לניטור',
    save: 'שמור',
    search_groups: 'חיפוש קבוצות',
    connect_wa_first: 'חבר WhatsApp בהגדרות כדי לטעון קבוצות.',
    // Configure tab
    match_confidence: 'רגישות זיהוי פנים',
    confidence_hint: 'גבוה יותר = פחות תוצאות שגויות. נמוך יותר = יותר זיהויים, כולל אולי ילדים אחרים.',
    more_matches: 'יותר זיהויים',
    fewer_false: 'פחות שגיאות',
    whatsapp_forward: 'העברה ב-WhatsApp',
    enabled: 'מופעל',
    forward_description: 'העבר תמונות שזוהו לצ\'אט (למשל, הצ\'אט הפרטי עם בן/בת הזוג).',
    select_chat: '-- בחר צ\'אט --',
    save_to_folder: 'שמור לתיקייה',
    save_folder_description: 'שמור כל תמונה שזוהתה לתיקייה מקומית.',
    browse: 'עיין…',
    organise_by: 'ארגן לפי',
    by_group: 'קבוצה',
    by_kid: 'ילד',
    daily_digest: 'תקציר יומי',
    digest_description: 'שמור התאמות ושלח פעם ביום במקום מיידית.',
    send_at: 'שלח ב',
    activity_thumbnails: 'תמונות ממוזערות',
    thumbnails_description: 'שמור תמונות ממוזערות של זיהויים ביומן הפעילות. נמחקות אוטומטית לאחר זמן מוגדר.',
    keep_for: 'שמור',
    hours: 'שעות',
    google_photos: 'Google Photos',
    gp_description: 'העלה כל תמונה שזוהתה ל-Google Photos.',
    organise_albums: 'ארגן אלבומים לפי',
    no_album: 'ללא אלבום',
    single_album: 'אלבום יחיד',
    album_name: 'שם אלבום',
    save_settings: 'שמור הגדרות',
    // Backup
    backup_restore: 'גיבוי ושחזור',
    backup_description: 'הגיבוי כולל את כל ההגדרות וילדים רשומים (תמונות ונתוני פנים). הפעלת WhatsApp אינה נכללת.',
    export_backup: 'ייצוא גיבוי',
    restore_backup: 'שחזור גיבוי',
    // Settings page
    whatsapp_connection: 'חיבור WhatsApp',
    wa_connected: 'מחובר',
    wa_not_connected: 'לא מחובר.',
    disconnect: 'השהה',
    sign_out: 'התנתק',
    connect: 'חבר',
    waiting_qr: 'ממתין לקוד QR…',
    scan_qr_instruction: 'פתח WhatsApp בטלפון ← מכשירים מקושרים ← קשר מכשיר',
    active_hours: 'שעות פעילות',
    active_hours_subtitle: 'ניתוק אוטומטי מחוץ לשעות אלו כדי שהטלפון יקבל התראות',
    from: 'מ',
    to: 'עד',
    bot_disconnects: 'הבוט מתנתק מחוץ לחלון זה',
    integrations: 'שירותים',
    integrations_subtitle: 'חבר שירותים חיצוניים. לאחר ההגדרה כאן, ניתן להפעיל כל תכונה בנפרד.',
    gp_not_connected_badge: 'לא מחובר',
    gp_connected_badge: 'מחובר',
    how_to_credentials: 'כיצד לקבל פרטי גישה ▸',
    gp_step_1: 'כנס ל-<a href="https://console.cloud.google.com" target="_blank" class="text-blue-600 underline hover:text-blue-800">console.cloud.google.com</a>, צור פרויקט חדש (או בחר קיים).',
    gp_step_2: 'כנס ל-<strong>APIs &amp; Services → Library</strong>, חפש <strong>Photos Library API</strong> ואפשר אותו.',
    gp_step_3: 'כנס ל-<strong>APIs &amp; Services → OAuth consent screen</strong>.<br>תחת <strong>Audience</strong>, הגדר את סוג המשתמש ל-<strong>External</strong> ומצב הפרסום ל-<strong>In production</strong>.',
    gp_step_4: 'כנס ל-<strong>APIs &amp; Services → Credentials → Create Credentials → OAuth Client ID</strong>.<br>סוג האפליקציה: <strong>Web application</strong>.',
    gp_step_5: 'תחת <strong>Authorized redirect URIs</strong>, הוסף בדיוק:<br><code class="bg-white border border-gray-200 px-1 rounded break-all select-all">http://localhost:8000/api/settings/google-photos/callback</code>',
    gp_step_6: 'העתק את ה-<strong>Client ID</strong> וה-<strong>Client Secret</strong> לשדות למטה, לחץ <strong>שמור הגדרות</strong>, ואז לחץ <strong>התחבר עם Google</strong>.',
    client_id: 'מזהה לקוח',
    client_secret: 'סוד לקוח',
    connect_google: 'חיבור עם Google',
    security: 'אבטחה',
    security_subtitle: 'נעל את הממשק עם PIN למניעת גישה לא מורשית ברשת.',
    pin_lock: 'נעילת PIN',
    pin_digits: 'PIN (4–6 ספרות)',
    pin_keep_hint: 'השאר ריק לשמירת ה-PIN הנוכחי.',
    // Tabs (new)
    tab_actions: 'פעולות',
    tab_settings: 'הגדרות',
    // Language
    language: 'שפה',
    // Dynamic subtitles
    nav_disconnected: 'מנותק',
    kids_subtitle_1: 'ילד 1 · {photos} תמונות רשומות',
    kids_subtitle_n: '{n} ילדים · {photos} תמונות רשומות',
    kid_photos_1: 'תמונה 1',
    kid_photos_n: '{n} תמונות',
    groups_subtitle_0: 'אין קבוצות מנוטרות · חפש להוסיף',
    groups_subtitle_1: 'קבוצה 1 מנוטרת · חפש להוסיף או להסיר',
    groups_subtitle_n: '{n} קבוצות מנוטרות · חפש להוסיף או להסיר',
    // WA status detail
    wa_session_disconnected: 'מנותק — הטלפון מקבל התראות. לחץ חבר כדי להמשיך.',
    wa_not_linked: 'לא מקושר. סרוק את קוד ה-QR כדי להתחבר.',
    // Test panel
    analyzing: 'מנתח…',
    no_faces_in_frame: 'לא זוהו פנים באף פריים',
    try_clearer_photo: 'נסה תמונה ברורה יותר',
    nothing_sent: '(לא יישלח כלום)',
    no_kids_enrolled_yet: 'אין ילדים רשומים עדיין',
    // Kid actions
    renamed: 'שם שונה',
    rename_failed: 'שינוי שם נכשל',
    photo_enrolled: 'תמונה נרשמה!',
    // Kids grid / card
    add_kid: 'הוסף ילד',
    face_count_1: 'פנים אחת',
    face_count_n: '⚠ {n} פנים',
    quality_too_small: 'קטן מדי',
    quality_small: 'קטן',
    quality_good: 'טוב',
    enroll_btn: 'רשום',
    discard_btn: 'בטל',
    del_orig_btn: 'מחק מקור',
    remove_btn: 'הסר',
    deleted_state: 'נמחק',
    original_deleted: 'מקור נמחק — הווקטור נשמר',
    already_deleted: 'כבר נמחק',
    originals_deleted_1: 'מקור 1 נמחק',
    originals_deleted_n: '{n} מקורות נמחקו',
    removed: 'הוסר',
    failed_remove: 'ההסרה נכשלה',
    enrollment_failed: 'הרישום נכשל',
    no_face_detected: 'לא זוהו פנים',
    upload_failed: 'ההעלאה נכשלה',
    failed_add_kid: 'הוספת ילד נכשלה',
    failed_delete: 'המחיקה נכשלה',
    kid_deleted: '{name} נמחק',
    delete_kid_confirm: 'למחוק את {name} וכל התמונות הרשומות שלו?',
    delete_all_originals_confirm: 'למחוק את כל תמונות המקור של {name}? הווקטורים נשמרים.',
    rename_tooltip: 'שנה שם',
    // Groups
    scan_all_groups: 'סרוק את כל הקבוצות לכל הילדים',
    scan_all_groups_hint: 'כשמופעל, כל קבוצה שהבוט נמצא בה תיסרק — לא רק הקבוצות המנוטרות למטה.',
    no_groups_match: 'אין קבוצות התואמות לחיפוש.',
    search_to_add_groups: 'חפש להוסיף קבוצות לניטור.',
    kids_count_1: 'ילד 1',
    kids_count_n: '{n} ילדים',
    groups_saved: 'קבוצות נשמרו!',
    failed_save: 'השמירה נכשלה',
    refresh_from_wa: 'רענן מ-WhatsApp',
    refresh_tooltip: 'רענן',
    // Actions / settings toasts
    enter_folder_path: 'הזן נתיב תיקייה לשמירת תמונות',
    settings_saved: 'הגדרות נשמרו!',
    failed_save_settings: 'שמירת ההגדרות נכשלה',
    folder_picker_unavailable: 'בוחר התיקיות לא זמין — הקלד את הנתיב ידנית',
    could_not_open_picker: 'לא ניתן לפתוח את בוחר התיקיות',
    // Digest banner
    send_now: 'שלח עכשיו',
    digest_on_prefix: 'מצב תקציר פעיל ·',
    photos_queued: 'תמונות בתור',
    // Activity
    clear_activity_confirm: 'למחוק את כל יומן הפעילות?',
    // WA actions
    disconnecting: 'משהה…',
    disconnected_phone_notif: 'הושהה — הטלפון שלך יקבל התראות עכשיו',
    could_not_disconnect: 'לא ניתן להשהות',
    signing_out: 'מתנתק…',
    signed_out_qr: 'התנתקת — סרוק QR להתחברות מחדש',
    could_not_sign_out: 'לא ניתן להתנתק',
    connecting_ellipsis: 'מתחבר…',
    reconnecting: 'מתחבר מחדש…',
    could_not_connect: 'לא ניתן להתחבר',
    wa_logout_confirm: 'פעולה זו תנתק את הבוט מחשבון WhatsApp שלך. יהיה עליך לסרוק קוד QR להתחברות מחדש. להמשיך?',
    // Model loading banner
    model_loading: 'הגדרה ראשונית: מוריד את מודל זיהוי הפנים (כ־500 MB). זה לא יקרה שוב.',
    model_error: 'טעינת מודל זיהוי פנים נכשלה.',
  },
};

function getLang() {
  return localStorage.getItem('myne_lang') || 'en';
}

function t(key) {
  const lang = getLang();
  return TRANSLATIONS[lang]?.[key] ?? TRANSLATIONS.en[key] ?? key;
}

function tpl(baseKey, n, extra = {}) {
  const key = n === 0 ? `${baseKey}_0` : n === 1 ? `${baseKey}_1` : `${baseKey}_n`;
  let s = t(key);
  if (s === key) s = t(`${baseKey}_n`);
  s = s.replace('{n}', n);
  for (const [k, v] of Object.entries(extra)) s = s.replace(`{${k}}`, v);
  return s;
}

function applyLang(lang) {
  localStorage.setItem('myne_lang', lang);
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'he' ? 'rtl' : 'ltr';

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const val = t(key);
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
      el.placeholder = val;
    } else {
      el.textContent = val;
    }
  });

  // Options need special handling since textContent replaces all children
  document.querySelectorAll('[data-i18n-opt]').forEach(el => {
    el.textContent = t(el.dataset.i18nOpt);
  });

  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    el.title = t(el.dataset.i18nTitle);
  });

  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    el.innerHTML = t(el.dataset.i18nHtml);
  });
}

// Apply immediately on load (before DOMContentLoaded) to avoid flicker
(function () {
  const lang = getLang();
  if (lang !== 'en') {
    document.documentElement.lang = lang;
    document.documentElement.dir = 'rtl';
  }
})();
