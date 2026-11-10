/**
 * CPGRAMS Reimagined - Core Frontend Script
 * IBM Db2Hack 2026 - AI & Modern Data Apps Track
 * Features:
 * - Accessibility (A-/A/A+ Text resizing, High Contrast mode, Dark Mode)
 * - Modern Toast Notification System (Replacing native alerts)
 * - All Indian Languages Universal Multilingual Engine (22+ Scheduled Languages)
 * - Real Web Speech Recognition (Live Speech-to-Text with Indian dialect mapping & simulation fallback)
 * - Live Keyword-Based Suggested Department Classifier
 * - Photo/Document Evidence Upload with Live Image Thumbnails & Removal
 * - 1-Click GPS Geolocation & Landmark Tagging
 * - Dynamic Grievance Storage & Unique GRV-2026-XXXX ID Generation
 * - Visual 4-Stage Timeline (Filed -> Under Review -> Forwarded to Dept -> Resolved)
 * - 12-Day Escalation Workflow & Confirmation
 * - Floating AI Assistant ("CPGRAMS Sahayak / मित्र") with Voice & Chat Intelligence
 * - Slide-in Quick Grievance History / Session Drawer
 */

(function () {
    'use strict';

    // ==========================================================================
    // 1. Language Map & Multilingual Dictionaries (All Indian Languages)
    // ==========================================================================
    const languageNames = {
        "en": "English",
        "hi": "हिन्दी (Hindi)",
        "bn": "বাংলা (Bengali)",
        "ta": "தமிழ் (Tamil)",
        "te": "తెలుగు (Telugu)",
        "mr": "मराठी (Marathi)",
        "gu": "ગુજરાતી (Gujarati)",
        "kn": "ಕನ್ನಡ (Kannada)",
        "ml": "മലയാളം (Malayalam)",
        "pa": "ਪੰਜਾਬੀ (Punjabi)",
        "or": "ଓଡ଼ିଆ (Odia)",
        "as": "অসমীয়া (Assamese)",
        "ur": "اردو (Urdu)",
        "sa": "संस्कृतम् (Sanskrit)",
        "mai": "मैथिली (Maithili)",
        "doi": "डोगरी (Dogri)",
        "kok": "कोंकणी (Konkani)",
        "ne": "नेपाली (Nepali)",
        "sd": "سنڌي (Sindhi)",
        "ks": "کٲشُر (Kashmiri)",
        "sat": "संथाली (Santali)",
        "brx": "बर' (Bodo)",
        "mni": "মৈতৈলোন্ (Manipuri)"
    };

    const voiceLocaleMap = {
        "en": "en-IN",
        "hi": "hi-IN",
        "bn": "bn-IN",
        "ta": "ta-IN",
        "te": "te-IN",
        "mr": "mr-IN",
        "gu": "gu-IN",
        "kn": "kn-IN",
        "ml": "ml-IN",
        "pa": "pa-IN",
        "ur": "ur-IN",
        "or": "or-IN",
        "as": "as-IN",
        "ne": "ne-NP",
        "sa": "hi-IN",
        "mai": "hi-IN",
        "doi": "hi-IN",
        "kok": "kok-IN",
        "sd": "sd-IN",
        "ks": "ks-IN",
        "sat": "sat-IN",
        "brx": "brx-IN",
        "mni": "mni-IN"
    };

    const i18nData = {
        en: {
            "gov_identity": "Government of India",
            "cpgrams_title": "CPGRAMS",
            "cpgrams_subtitle": "Centralized Public Grievance Redress & Monitoring System",
            "nav_home": "Home",
            "nav_lodge": "Lodge Grievance",
            "nav_track": "Track Status",
            "nav_help": "Help & FAQs",
            "nav_contact": "Contact",
            "hero_badge": "Official Government Portal",
            "hero_title": "File a complaint about a government service and track its progress online.",
            "hero_subtitle": "CPGRAMS makes it easy for every citizen to raise public grievances related to central government departments and ministries, and track them until resolution.",
            "hero_btn_lodge": "Lodge a Grievance",
            "hero_btn_track": "Track Your Status",
            "hero_note": "Filing a grievance is completely free. Save your registration number to track your case.",
            "how_eyebrow": "SIMPLE PROCESS",
            "how_title": "How CPGRAMS Works",
            "how_subtitle": "Three simple steps to file and resolve your grievance",
            "step1_title": "Submit Your Grievance",
            "step1_desc": "Fill out a simple form describing your issue with a central government service. You can also attach supporting documents.",
            "step2_title": "Track Progress",
            "step2_desc": "Use your registration number to check the status of your grievance at any time. You'll see which department is handling your case.",
            "step3_title": "Receive a Response",
            "step3_desc": "The concerned department reviews and addresses your grievance. You'll be notified of the outcome and can provide feedback.",
            "quick_title": "Quick Actions",
            "quick_lodge": "Lodge a New Grievance",
            "quick_track": "Track Existing Grievance",
            "quick_faq": "View Help & FAQs",
            "quick_contact": "Contact Support",
            "footer_copyright": "© 2026 Government of India. All rights reserved.",
            "footer_privacy": "Privacy Policy",
            "footer_terms": "Terms of Use",
            "footer_a11y": "Accessibility Statement",
            "lodge_heading": "Lodge a Grievance",
            "lodge_subheading": "Submit your complaint about a central government service in a few simple steps.",
            "track_heading": "Track Your Grievance",
            "track_subheading": "Check the current status of your grievance using your registration number.",
            "contact_heading": "Contact & Support",
            "faq_heading": "Help & Frequently Asked Questions",
            "btn_continue": "Continue",
            "btn_back": "Back",
            "btn_submit": "Submit Grievance",
            "voice_btn": "🎙️ Voice Input (Speak)",
            "voice_listening": "Listening... Speak your grievance in English or हिन्दी...",
            "suggested_dept_label": "Suggested Department:",
            "btn_apply_suggestion": "Apply Suggestion",
            "escalate_btn": "Escalate This Grievance",
            "escalate_warning": "This grievance has been pending for 12 days without resolution.",
            "stage_filed": "Filed",
            "stage_review": "Under Review",
            "stage_forwarded": "Forwarded to Dept",
            "stage_resolved": "Resolved",
            "sahayak_title": "CPGRAMS Sahayak",
            "sahayak_greeting": "Namaste! I am your CPGRAMS AI Assistant. How can I help you today? You can ask about filing a complaint, tracking status, or finding the right department.",
            "sahayak_placeholder": "Type or speak your question..."
        },
        hi: {
            "gov_identity": "भारत सरकार",
            "cpgrams_title": "सीपीजीआरएएमएस (CPGRAMS)",
            "cpgrams_subtitle": "केंद्रीकृत लोक शिकायत निवारण और निगरानी प्रणाली",
            "nav_home": "मुख्य पृष्ठ",
            "nav_lodge": "शिकायत दर्ज करें",
            "nav_track": "स्थिति ट्रैक करें",
            "nav_help": "सहायता और अक्सर पूछे जाने वाले प्रश्न",
            "nav_contact": "संपर्क करें",
            "hero_badge": "भारत सरकार का आधिकारिक पोर्टल",
            "hero_title": "सरकारी सेवा से संबंधित शिकायत दर्ज करें और ऑनलाइन प्रगति देखें।",
            "hero_subtitle": "सीपीजीआरएएमएस प्रत्येक नागरिक के लिए केंद्र सरकार के मंत्रालयों एवं विभागों से संबंधित सार्वजनिक शिकायतें दर्ज करना और समाधान तक ट्रैक करना आसान बनाता है।",
            "hero_btn_lodge": "शिकायत दर्ज करें",
            "hero_btn_track": "शिकायत की स्थिति जांचें",
            "hero_note": "शिकायत दर्ज करना पूरी तरह निःशुल्क है। अपनी शिकायत ट्रैक करने के लिए पंजीकरण संख्या सुरक्षित रखें।",
            "how_eyebrow": "सरल प्रक्रिया",
            "how_title": "सीपीजीआरएएमएस कैसे काम करता है",
            "how_subtitle": "शिकायत दर्ज करने और समाधान पाने के तीन सरल चरण",
            "step1_title": "अपनी शिकायत दर्ज करें",
            "step1_desc": "केंद्र सरकार की सेवा से संबंधित अपनी समस्या का विवरण देते हुए एक सरल फॉर्म भरें। आप दस्तावेज भी संलग्न कर सकते हैं।",
            "step2_title": "प्रगति ट्रैक करें",
            "step2_desc": "किसी भी समय अपनी शिकायत की स्थिति जांचने के लिए पंजीकरण संख्या का उपयोग करें। आपको संबंधित विभाग की जानकारी दिखेगी।",
            "step3_title": "समाधान और उत्तर प्राप्त करें",
            "step3_desc": "संबंधित विभाग आपकी शिकायत की समीक्षा कर समाधान प्रदान करता है। आपको परिणाम की सूचना मिलेगी और आप फीडबैक दे सकते हैं।",
            "quick_title": "त्वरित कार्य",
            "quick_lodge": "नई शिकायत दर्ज करें",
            "quick_track": "शिकायत की स्थिति ट्रैक करें",
            "quick_faq": "सहायता और एफएक्यू देखें",
            "quick_contact": "सहायता टीम से संपर्क करें",
            "footer_copyright": "© 2026 भारत सरकार। सर्वाधिकार सुरक्षित।",
            "footer_privacy": "गोपनीयता नीति",
            "footer_terms": "उपयोग की शर्तें",
            "footer_a11y": "पहुंच-योग्यता विवरण",
            "lodge_heading": "लोक शिकायत दर्ज करें",
            "lodge_subheading": "कुछ सरल चरणों में केंद्र सरकार की सेवा से संबंधित अपनी शिकायत दर्ज करें।",
            "track_heading": "शिकायत की स्थिति ट्रैक करें",
            "track_subheading": "अपनी पंजीकरण संख्या दर्ज करके शिकायत की वर्तमान स्थिति जांचें।",
            "contact_heading": "संपर्क एवं सहायता",
            "faq_heading": "सहायता एवं अक्सर पूछे जाने वाले प्रश्न (FAQ)",
            "btn_continue": "आगे बढ़ें",
            "btn_back": "पीछे जाएं",
            "btn_submit": "शिकायत जमा करें",
            "voice_btn": "🎙️ बोलकर लिखें (Voice Input)",
            "voice_listening": "सुन रहे हैं... कृपया अपनी समस्या बोलें...",
            "suggested_dept_label": "सुझाया गया विभाग:",
            "btn_apply_suggestion": "यह विभाग चुनें",
            "escalate_btn": "यह शिकायत एस्केलेट करें",
            "escalate_warning": "यह शिकायत 12 दिनों से बिना समाधान के लंबित है।",
            "stage_filed": "दर्ज किया गया",
            "stage_review": "समीक्षाधीन (Under Review)",
            "stage_forwarded": "विभाग को अग्रेषित",
            "stage_resolved": "समाधान पूर्ण",
            "sahayak_title": "सीपीजीआरएएमएस सहायक (Sahayak)",
            "sahayak_greeting": "नमस्ते! मैं आपका सीपीजीआरएएमएस सहायक हूँ। आज मैं आपकी क्या मदद कर सकता हूँ? आप शिकायत दर्ज करने, स्थिति ट्रैक करने या सही विभाग चुनने के बारे में पूछ सकते हैं।",
            "sahayak_placeholder": "अपना प्रश्न लिखें या बोलें..."
        },
        bn: {
            "gov_identity": "ভারত সরকার",
            "cpgrams_title": "সিপিজিআরএএমএস (CPGRAMS)",
            "cpgrams_subtitle": "কেন্দ্রীভূত জনঅভিযোগ প্রতিকার ও পর্যবেক্ষণ ব্যবস্থা",
            "nav_home": "মূল পাতা",
            "nav_lodge": "অভিযোগ দায়ের করুন",
            "nav_track": "অবস্থা ট্র্যাক করুন",
            "nav_help": "সহায়তা ও প্রশ্নোত্তর",
            "nav_contact": "যোগাযোগ",
            "hero_badge": "ভারত সরকারের সরকারি পোর্টাল",
            "hero_title": "সরকারি পরিষেবা সংক্রান্ত অভিযোগ দায়ের করুন এবং অনলাইনে অগ্রগতি দেখুন।",
            "hero_btn_lodge": "অভিযোগ দায়ের করুন",
            "hero_btn_track": "অবস্থা পরীক্ষা করুন",
            "btn_continue": "এগিয়ে যান",
            "btn_back": "পেছনে যান",
            "btn_submit": "অভিযোগ জমা দিন",
            "voice_btn": "🎙️ মুখে বলে লিখুন (Voice)",
            "sahayak_title": "সিপিজিআরএএমএস সহায়ক",
            "sahayak_greeting": "নমস্কার! আমি আপনার সিপিজিআরএএমএস এআই সহায়ক। আজ আপনাকে কীভাবে সাহায্য করতে পারি?"
        },
        ta: {
            "gov_identity": "இந்திய அரசு",
            "cpgrams_title": "சிபிகிராம்ஸ் (CPGRAMS)",
            "cpgrams_subtitle": "மத்திய பொது குறைதீர்ப்பு மற்றும் கண்காணிப்பு அமைப்பு",
            "nav_home": "முகப்பு",
            "nav_lodge": "புகார் பதிவு செய்க",
            "nav_track": "நிலையைக் கண்காணிக்கவும்",
            "nav_help": "உதவி & கேள்விகள்",
            "nav_contact": "தொடர்பு கொள்ள",
            "hero_badge": "இந்திய அரசு அதிகாரப்பூர்வ தளம்",
            "hero_title": "அரசு சேவைகள் குறித்த புகாரைப் பதிவு செய்து, அதன் முன்னேற்றத்தைக் கண்காணிக்கவும்.",
            "hero_btn_lodge": "புகார் பதிவு செய்க",
            "hero_btn_track": "நிலையை சரிபார்க்கவும்",
            "btn_continue": "தொடரவும்",
            "btn_back": "பின்செல்க",
            "btn_submit": "புகாரைச் சமர்ப்பிக்கவும்",
            "voice_btn": "🎙️ பேசி எழுதவும் (Voice)",
            "sahayak_title": "சிபிகிராம்ஸ் சகாயக்",
            "sahayak_greeting": "வணக்கம்! நான் உங்கள் சிபிகிராம்ஸ் AI உதவியாளர். உங்களுக்கு எவ்வாறு உதவ முடியும்?"
        },
        te: {
            "gov_identity": "భారత ప్రభుత్వం",
            "cpgrams_title": "సిపిజిఆర్ఎఎంఎస్ (CPGRAMS)",
            "cpgrams_subtitle": "కేంద్రీకృత ప్రజా ఫిర్యాదుల పరిష్కార మరియు పర్యవేక్షణ వ్యవస్థ",
            "nav_home": "హోమ్",
            "nav_lodge": "ఫిర్యాదు నమోదు చేయండి",
            "nav_track": "స్థితిని ట్రాక్ చేయండి",
            "nav_help": "సహాయం & తరచుగా అడిగే ప్రశ్నలు",
            "nav_contact": "సంప్రదించండి",
            "hero_badge": "భారత ప్రభుత్వ అధికారిక పోర్టల్",
            "hero_title": "ప్రభుత్వ సేవలపై ఫిర్యాదు నమోదు చేసి ఆన్‌లైన్‌లో పురోగతిని ట్రాక్ చేయండి.",
            "hero_btn_lodge": "ఫిర్యాదు చేయండి",
            "hero_btn_track": "స్థితిని తనిఖీ చేయండి",
            "btn_continue": "కొనసాగించండి",
            "btn_back": "వెనుకకు",
            "btn_submit": "ఫిర్యాదును సమర్పించండి",
            "voice_btn": "🎙️ మాట్లాడి రాయండి (Voice)",
            "sahayak_title": "సిపిజిఆర్ఎఎంఎస్ సహాయక్",
            "sahayak_greeting": "నమస్కారం! నేను మీ సిపిజిఆర్ఎఎంఎస్ AI సహాయకుడిని. నేను మీకు ఎలా సహాయపడగలను?"
        },
        mr: {
            "gov_identity": "भारत सरकार",
            "cpgrams_title": "सीपीजीआरएएमएस (CPGRAMS)",
            "cpgrams_subtitle": "केंद्रीकृत सार्वजनिक तक्रार निवारण आणि देखरेख प्रणाली",
            "nav_home": "मुख्यपृष्ठ",
            "nav_lodge": "तक्रार दाखल करा",
            "nav_track": "स्थिती ट्रॅक करा",
            "nav_help": "मदत आणि वारंवार विचारले जाणारे प्रश्न",
            "nav_contact": "संपर्क",
            "hero_badge": "भारत सरकारचे अधिकृत पोर्टल",
            "hero_title": "शासकीय सेवेबाबत तक्रार नोंदवा आणि ऑनलाइन प्रगती तपासा.",
            "hero_btn_lodge": "तक्रार दाखल करा",
            "hero_btn_track": "स्थिती तपासा",
            "btn_continue": "पुढे जा",
            "btn_back": "मागे जा",
            "btn_submit": "तक्रार सादर करा",
            "voice_btn": "🎙️ बोलून लिहा (Voice)",
            "sahayak_title": "सीपीजीआरएएमएस सहाय्यक",
            "sahayak_greeting": "नमस्कार! मी आपला सीपीजीआरएएमएस AI सहाय्यक आहे. मी आज आपल्याला कशी मदत करू शकतो?"
        },
        gu: {
            "gov_identity": "ભારત સરકાર",
            "cpgrams_title": "સીપીજીઆરએએમએસ (CPGRAMS)",
            "cpgrams_subtitle": "કેન્દ્રીયકૃત જાહેર ફરિયાદ નિવારણ અને દેખરેખ પ્રણાલી",
            "nav_home": "મુખ્ય પૃષ્ઠ",
            "nav_lodge": "ફરિયાદ નોંધાવો",
            "nav_track": "સ્થિતિ ટ્રેક કરો",
            "nav_help": "મદદ અને પ્રશ્નોત્તરી",
            "nav_contact": "સંપર્ક",
            "hero_badge": "ભારત સરકારનું સત્તાવાર પોર્ટલ",
            "hero_title": "સરકારી સેવા વિશે ફરિયાદ નોંધાવો અને ઓનલાઇન પ્રગતિ જુઓ.",
            "hero_btn_lodge": "ફરિયાદ નોંધાવો",
            "hero_btn_track": "સ્થિતિ તપાસો",
            "btn_continue": "આગળ વધો",
            "btn_back": "પાછા જાઓ",
            "btn_submit": "ફરિયાદ સબમિટ કરો",
            "voice_btn": "🎙️ બોલીને લખો (Voice)",
            "sahayak_title": "સીપીજીઆરએએમએસ સહાયક",
            "sahayak_greeting": "નમસ્તે! હું તમારો સીપીજીઆરએએમએસ AI સહાયક છું. હું આજે તમારી કેવી રીતે મદદ કરી શકું?"
        },
        kn: {
            "gov_identity": "ಭಾರತ ಸರ್ಕಾರ",
            "cpgrams_title": "ಸಿಪಿಜಿಆರ್‌ಎಎಮ್‌ಎಸ್ (CPGRAMS)",
            "cpgrams_subtitle": "ಕೇಂದ್ರೀಕೃತ ಸಾರ್ವಜನಿಕ ಕುಂದುಕೊರತೆ ನಿವಾರಣೆ ಮತ್ತು ಮೇಲ್ವಿಚಾರಣಾ ವ್ಯವಸ್ಥೆ",
            "nav_home": "ಮುಖಪುಟ",
            "nav_lodge": "ದೂರು ದಾಖಲಿಸಿ",
            "nav_track": "ಸ್ಥಿತಿಯನ್ನು ಟ್ರ್ಯಾಕ್ ಮಾಡಿ",
            "nav_help": "ಸಹಾಯ ಮತ್ತು ಸಾಮಾನ್ಯ ಪ್ರಶ್ನೆಗಳು",
            "nav_contact": "ಸಂಪರ್ಕಿಸಿ",
            "hero_badge": "ಭಾರತ ಸರ್ಕಾರದ ಅಧಿಕೃತ ಪೋರ್ಟಲ್",
            "hero_title": "ಸರ್ಕಾರಿ ಸೇವೆಗಳ ಕುರಿತು ದೂರು ದಾಖಲಿಸಿ ಮತ್ತು ಆನ್‌ಲೈನ್‌ನಲ್ಲಿ ಪ್ರಗತಿಯನ್ನು ಟ್ರ್ಯಾಕ್ ಮಾಡಿ.",
            "hero_btn_lodge": "ದೂರು ದಾಖಲಿಸಿ",
            "hero_btn_track": "ಸ್ಥಿತಿ ಪರಿಶೀಲಿಸಿ",
            "btn_continue": "ಮುಂದುವರಿಯಿರಿ",
            "btn_back": "ಹಿಂದಕ್ಕೆ",
            "btn_submit": "ದೂರು ಸಲ್ಲಿಸಿ",
            "voice_btn": "🎙️ ಧ್ವನಿ ಇನ್‌ಪುಟ್ (Voice)",
            "sahayak_title": "ಸಿಪಿಜಿಆರ್‌ಎಎಮ್‌ಎಸ್ ಸಹಾಯಕ",
            "sahayak_greeting": "ನಮಸ್ಕಾರ! ನಾನು ನಿಮ್ಮ ಸಿಪಿಜಿಆರ್‌ಎಎಮ್‌ಎಸ್ AI ಸಹಾಯಕ. ನಾನು ಇಂದು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?"
        },
        ml: {
            "gov_identity": "ഭാരത സർക്കാർ",
            "cpgrams_title": "സിപിജിആർഎഎംഎസ് (CPGRAMS)",
            "cpgrams_subtitle": "കേന്ദ്രീകൃത പബ്ലിക് ഗ്രീവൻസ് പരിഹാരവും നിരീക്ഷണ സംവിധാനവും",
            "nav_home": "ഹോം",
            "nav_lodge": "പരാതി നൽകുക",
            "nav_track": "സ്റ്റാറ്റസ് ട്രാക്ക് ചെയ്യുക",
            "nav_help": "സഹായവും ചോദ്യങ്ങളും",
            "nav_contact": "ബന്ധപ്പെടുക",
            "hero_badge": "ഭാരത സർക്കാരിന്റെ ഔദ്യോഗിക പോർട്ടൽ",
            "hero_title": "സർക്കാർ സേവനങ്ങളെക്കുറിച്ച് പരാതി നൽകി പുരോഗതി ഓൺലൈനായി ട്രാക്ക് ചെയ്യുക.",
            "hero_btn_lodge": "പരാതി നൽകുക",
            "hero_btn_track": "സ്റ്റാറ്റസ് പരിശോധിക്കുക",
            "btn_continue": "തുടരുക",
            "btn_back": "പിന്നോട്ട്",
            "btn_submit": "പരാതി സമർപ്പിക്കുക",
            "voice_btn": "🎙️ സംസാരിച്ച് എഴുതുക (Voice)",
            "sahayak_title": "സിപിജിആർഎഎംഎസ് സഹായക്",
            "sahayak_greeting": "നമസ്കാരം! ഞാൻ നിങ്ങളുടെ സിപിജിആർഎഎംഎസ് AI അസിസ്റ്റന്റാണ്. ഞാൻ നിങ്ങളെ എങ്ങനെ സഹായിക്കണം?"
        },
        pa: {
            "gov_identity": "ਭਾਰਤ ਸਰਕਾਰ",
            "cpgrams_title": "ਸੀਪੀਜੀਆਰਏਐਮਐਸ (CPGRAMS)",
            "cpgrams_subtitle": "ਕੇਂਦਰੀਕ੍ਰਿਤ ਜਨਤਕ ਸ਼ਿਕਾਇਤ ਨਿਵਾਰਨ ਅਤੇ ਨਿਗਰਾਨੀ ਪ੍ਰਣਾਲੀ",
            "nav_home": "ਮੁੱਖ ਪੰਨਾ",
            "nav_lodge": "ਸ਼ਿਕਾਇਤ ਦਰਜ ਕਰੋ",
            "nav_track": "ਸਥਿਤੀ ਟ੍ਰੈਕ ਕਰੋ",
            "nav_help": "ਮਦਦ ਅਤੇ ਅਕਸਰ ਪੁੱਛੇ ਜਾਂਦੇ ਸਵਾਲ",
            "nav_contact": "ਸੰਪਰਕ ਕਰੋ",
            "hero_badge": "ਭਾਰਤ ਸਰਕਾਰ ਦਾ ਅਧਿਕਾਰਤ ਪੋਰਟਲ",
            "hero_title": "ਸਰਕਾਰੀ ਸੇਵਾ ਬਾਰੇ ਸ਼ਿਕਾਇਤ ਦਰਜ ਕਰੋ ਅਤੇ ਔਨਲਾਈਨ ਪ੍ਰਗਤੀ ਵੇਖੋ।",
            "hero_btn_lodge": "ਸ਼ਿਕਾਇਤ ਦਰਜ ਕਰੋ",
            "hero_btn_track": "ਸਥਿਤੀ ਦੀ ਜਾਂਚ ਕਰੋ",
            "btn_continue": "ਅੱਗੇ ਵਧੋ",
            "btn_back": "ਪਿੱਛੇ ਜਾਓ",
            "btn_submit": "ਸ਼ਿਕਾਇਤ ਜਮ੍ਹਾਂ ਕਰੋ",
            "voice_btn": "🎙️ ਬੋਲ ਕੇ ਲਿਖੋ (Voice)",
            "sahayak_title": "ਸੀਪੀਜੀਆਰਏਐਮਐਸ ਸਹਾਇਕ",
            "sahayak_greeting": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ! ਮੈਂ ਤੁਹਾਡਾ ਸੀਪੀਜੀਆਰਏਐਮਐਸ AI ਸਹਾਇਕ ਹਾਂ। ਮੈਂ ਅੱਜ ਤੁਹਾਡੀ ਕੀ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ?"
        },
        or: {
            "gov_identity": "ଭାରତ ସରକାର",
            "cpgrams_title": "ସିପିଜିଆରଏଏମଏସ (CPGRAMS)",
            "cpgrams_subtitle": "କେନ୍ଦ୍ରୀକୃତ ଜନ ଅଭିଯୋଗ ନିବାରଣ ଏବଂ ତଦାରଖ ପ୍ରଣାଳୀ",
            "nav_home": "ମୁଖ୍ୟ ପୃଷ୍ଠା",
            "nav_lodge": "ଅଭିଯୋଗ ଦାଖଲ କରନ୍ତୁ",
            "nav_track": "ସ୍ଥିତି ଟ୍ରାକ୍ କରନ୍ତୁ",
            "nav_help": "ସହାୟତା ଏବଂ ପ୍ରଶ୍ନୋତ୍ତର",
            "nav_contact": "ଯୋଗାଯୋଗ",
            "hero_badge": "ଭାରତ ସରକାରଙ୍କ ସରକାରୀ ପୋର୍ଟାଲ",
            "hero_title": "ସରକାରୀ ସେବା ବିଷୟରେ ଅଭିଯୋଗ ଦାଖଲ କରନ୍ତୁ ଏବଂ ଅନଲାଇନରେ ସ୍ଥିତି ଯାଞ୍ଚ କରନ୍ତୁ।",
            "hero_btn_lodge": "ଅଭିଯୋଗ ଦାଖଲ କରନ୍ତୁ",
            "hero_btn_track": "ସ୍ଥିତି ଯାଞ୍ଚ କରନ୍ତୁ",
            "btn_continue": "ଆଗକୁ ବଢ଼ନ୍ତୁ",
            "btn_back": "ପଛକୁ ଯାଆନ୍ତୁ",
            "btn_submit": "ଅଭିଯୋଗ ଦାଖଲ କରନ୍ତୁ",
            "voice_btn": "🎙️ କହିକି ଲେଖନ୍ତୁ (Voice)",
            "sahayak_title": "ସିପିଜିଆରଏଏମଏସ ସହାୟକ",
            "sahayak_greeting": "ନମସ୍କାର! ମୁଁ ଆପଣଙ୍କର ସିପିଜିଆରଏଏମଏସ AI ସହାୟକ। ମୁଁ ଆପଣଙ୍କୁ କିପରି ସାହାଯ୍ୟ କରିପାରିବି?"
        },
        as: {
            "gov_identity": "ভাৰত চৰকাৰ",
            "cpgrams_title": "চিপিজিআৰএএমএছ (CPGRAMS)",
            "cpgrams_subtitle": "কেন্দ্ৰীভূত ৰাজহুৱা ওজৰ-আপত্তি নিষ্পত্তি আৰু নিৰীক্ষণ ব্যৱস্থা",
            "nav_home": "বেটুপাত",
            "nav_lodge": "অভিযোগ দাখিল কৰক",
            "nav_track": "স্থিতি পৰীক্ষা কৰক",
            "nav_help": "সহায় আৰু সঘনাই সোধা প্ৰশ্ন",
            "nav_contact": "যোগাযোগ",
            "hero_badge": "ভাৰত চৰকাৰৰ চৰকাৰী পৰ্টেল",
            "hero_title": "চৰকাৰী সেৱাৰ বিষয়ে অভিযোগ দাখিল কৰক আৰু অনলাইন স্থিতি পৰীক্ষা কৰক।",
            "hero_btn_lodge": "অভিযোগ দাখিল কৰক",
            "hero_btn_track": "স্থিতি পৰীক্ষা কৰক",
            "btn_continue": "আগলৈ যাওক",
            "btn_back": "পিছলৈ যাওক",
            "btn_submit": "অভিযোগ জমা দিয়ক",
            "voice_btn": "🎙️ কথা কৈ লিখক (Voice)",
            "sahayak_title": "চিপিজিআৰএএমএছ সহায়ক",
            "sahayak_greeting": "নমস্কাৰ! মই আপোনাৰ চিপিজিআৰএএমএছ AI সহায়ক। মই আপোনাক কেনেকৈ সহায় কৰিব পাৰোঁ?"
        },
        ur: {
            "gov_identity": "حکومت ہند",
            "cpgrams_title": "سی پی جی آر اے ایم ایس (CPGRAMS)",
            "cpgrams_subtitle": "مرکزی عوامی شکایت کے ازالے اور نگرانی کا نظام",
            "nav_home": "صفحہ اول",
            "nav_lodge": "شکایت درج کریں",
            "nav_track": "حیثیت معلوم کریں",
            "nav_help": "مدد اور عمومی سوالات",
            "nav_contact": "رابطہ کریں",
            "hero_badge": "حکومت ہند کا سرکاری پورٹل",
            "hero_title": "سرکاری خدمات سے متعلق شکایت درج کریں اور آن لائن پیش رفت دیکھیں۔",
            "hero_btn_lodge": "شکایت درج کریں",
            "hero_btn_track": "حیثیت چیک کریں",
            "btn_continue": "آگے بڑھیں",
            "btn_back": "پیچھے جائیں",
            "btn_submit": "شکایت جمع کریں",
            "voice_btn": "🎙️ بول کر لکھیں (Voice)",
            "sahayak_title": "سی پی جی آر اے ایم ایس معاون",
            "sahayak_greeting": "آداب! میں آپ کا سی پی جی آر اے ایم ایس AI معاون ہوں۔ آج میں آپ کی کیا مدد کر سکتا ہوں؟"
        }
    };

    // ==========================================================================
    // 2. Department Keyword Matcher Engine
    // ==========================================================================
    const deptKeywordRules = [
        {
            deptCode: "food",
            deptName: "Department of Food & Public Distribution",
            deptNameHi: "खाद्य एवं सार्वजनिक वितरण विभाग",
            keywords: ["ration", "ration card", "rashan", "food", "pds", "grain", "wheat", "rice", "sugar", "quota", "fair price shop", "राशन", "खाद्य", "राशन कार्ड", "রেশন", "రేషన్", "ரேஷன்", "रेशन"]
        },
        {
            deptCode: "pension",
            deptName: "Department of Pension & Pensioners' Welfare",
            deptNameHi: "पेंशन एवं पेंशनभोगी कल्याण विभाग",
            keywords: ["pension", "epfo", "provident fund", "pf", "retirement", "gratuity", "pensioner", "eps", "पेंशन", "भविष्य निधि", "পেনশন", "పెన్షన్", "ஓய்வூதியம்"]
        },
        {
            deptCode: "water",
            deptName: "Ministry of Jal Shakti (Water Resources)",
            deptNameHi: "जल शक्ति मंत्रालय (जल संसाधन)",
            keywords: ["water", "pipeline", "sewage", "drainage", "leakage", "drinking water", "jal", "tanker", "contamination", "नल", "पानी", "जल", "জল", "నీరు", "தண்ணீர்", "पाणी"]
        },
        {
            deptCode: "road",
            deptName: "Ministry of Road Transport & Highways / PWD",
            deptNameHi: "सड़क परिवहन एवं राजमार्ग मंत्रालय / लोक निर्माण विभाग",
            keywords: ["road", "highway", "pothole", "pavement", "bridge", "pwd", "nhai", "street", "traffic light", "flyover", "सड़क", "गड्ढा", "हाईवे", "রাস্তা", "రోడ్డు", "சாலை", "रस्ता"]
        },
        {
            deptCode: "electricity",
            deptName: "Ministry of Power / Electricity Board",
            deptNameHi: "विद्युत मंत्रालय / बिजली बोर्ड",
            keywords: ["electricity", "power", "transformer", "meter", "blackout", "voltage", "power cut", "electric bill", "power supply", "बिजली", "मीटर", "करंट", "বিদ্যুৎ", "విద్యుత్", "மின்சாரம்", "वीज"]
        },
        {
            deptCode: "mea",
            deptName: "Ministry of External Affairs (Passport Division)",
            deptNameHi: "विदेश मंत्रालय (पासपोर्ट प्रभाग)",
            keywords: ["passport", "visa", "consular", "mea", "embassy", "passport office", "rpo", "police verification passport", "पासपोर्ट", "वीजा", "பாஸ்போர்ட்", "పాస్‌పోర్ట్"]
        },
        {
            deptCode: "education",
            deptName: "Ministry of Education",
            deptNameHi: "शिक्षा मंत्रालय",
            keywords: ["school", "education", "teacher", "college", "university", "exam", "scholarship", "cbse", "ugc", "student", "degree", "admission", "शिक्षा", "स्कूल", "छात्रवृत्ति", "শিক্ষা", "విద్య", "கல்வி", "शिक्षण"]
        },
        {
            deptCode: "health",
            deptName: "Ministry of Health & Family Welfare",
            deptNameHi: "स्वास्थ्य एवं परिवार कल्याण मंत्रालय",
            keywords: ["hospital", "medical", "doctor", "health", "medicine", "clinic", "aiims", "treatment", "ayushman", "ambulance", "nurse", "अस्पताल", "स्वास्थ्य", "इलाज", "दवा", "হাসপাতাল", "ఆసుపత్రి", "மருத்துவமனை", "रुग्णालय"]
        },
        {
            deptCode: "finance",
            deptName: "Department of Financial Services / Banking Ombudsman",
            deptNameHi: "वित्तीय सेवाएं विभाग / बैंकिंग लोकपाल",
            keywords: ["bank", "loan", "atm", "account", "emi", "fraud", "transaction", "rbi", "sbi", "credit card", "cheque", "bank branch", "बैंक", "ऋण", "लोन", "खाता", "ব্যাংক", "బ్యాంకు", "வங்கி"]
        },
        {
            deptCode: "petroleum",
            deptName: "Ministry of Petroleum & Natural Gas",
            deptNameHi: "पेट्रोलियम एवं प्राकृतिक गैस मंत्रालय",
            keywords: ["gas", "lpg", "cylinder", "petrol", "diesel", "indane", "hp gas", "bharat gas", "ujjwala", "booking gas", "गैस", "सिलेंडर", "पेट्रोल", "গ্যাস", "గ్యాస్", "எரிவாயு"]
        },
        {
            deptCode: "railways",
            deptName: "Ministry of Railways",
            deptNameHi: "रेल मंत्रालय",
            keywords: ["train", "railway", "ticket", "station", "irctc", "berth", "coach", "pnr", "refund ticket", "रेल", "ट्रेन", "टिकट", "ট্রেন", "రైలు", "ரயில்", "रेल्वे"]
        },
        {
            deptCode: "posts",
            deptName: "Department of Posts",
            deptNameHi: "डाक विभाग",
            keywords: ["post", "speed post", "parcel", "dak", "courier", "post office", "tracking post", "डाक", "पार्सल", "पोस्ट ऑफिस", "ডাক", "పోస్ట్", "தபால்"]
        },
        {
            deptCode: "telecom",
            deptName: "Department of Telecommunications",
            deptNameHi: "दूरसंचार विभाग",
            keywords: ["telecom", "sim", "network", "bsnl", "broadband", "tower", "call drop", "mobile network", "इंटरनेट", "नेटवर्क"]
        },
        {
            deptCode: "mha",
            deptName: "Ministry of Home Affairs",
            deptNameHi: "गृह मंत्रालय",
            keywords: ["police", "security", "fir", "mha", "border", "law and order", "police station", "पुलिस", "सुरक्षा"]
        }
    ];

    // Sample Grievances for Voice Input simulation
    const sampleVoiceGrievances = [
        {
            subject: "Delay in Ration Card Verification and Issuance",
            description: "I submitted an application for a new family ration card 3 months ago at the zonal Food and Civil Supplies office (Application Ref #RC-98421). The local field verification was completed over 45 days ago, but the card status is still shown as pending. Multiple visits to the office have yielded no response. Please expedite the approval and issuance of my ration card.",
            category: "delay"
        },
        {
            subject: "Irregular Pension Disbursement and Arrears Not Credited",
            description: "My monthly superannuation pension for the last 4 months has not been credited to my bank account. Despite submitting my digital life certificate (Jeevan Pramaan) on time, the Pension Department and disbursing authority have withheld the payout without any official notice.",
            category: "scheme"
        },
        {
            subject: "Severe Drinking Water Supply Contamination and Pipeline Leakage",
            description: "For the past two weeks, the municipal water supply in our sector has been heavily contaminated with sewage drainage due to an underground pipeline breach. Multiple complaints filed with the local water board have been ignored while residents face severe health hazards.",
            category: "delay"
        },
        {
            subject: "Delay in Passport Renewal Dispatch After Police Clearance",
            description: "My passport renewal application (ARN: 25-0019482910) was submitted and approved at the Passport Seva Kendra. Police verification was completed successfully 28 days ago, but the booklet has still not been printed or dispatched. I need it urgently for an official travel.",
            category: "delay"
        }
    ];

    // ==========================================================================
    // 3. Application State & Storage
    // ==========================================================================
    const STORAGE_KEY_GRIEVANCES = "cpgrams_grievances_v1";
    const STORAGE_KEY_LANG = "cpgrams_preferred_lang";
    const STORAGE_KEY_CONTRAST = "cpgrams_contrast_mode";
    const STORAGE_KEY_THEME = "cpgrams_theme_mode";
    const STORAGE_KEY_FONT_SIZE = "cpgrams_font_size";

    const defaultDemoGrievance = {
        id: "GRV-2026-4821",
        subject: "Delay in Passport Renewal Dispatch",
        description: "Application verified by regional passport office but dispatch pending for over 28 days.",
        department: "Ministry of External Affairs (Passport Division)",
        category: "Delay in service",
        name: "Amitabh Verma",
        email: "amitabh.v@example.com",
        mobile: "+91 98765 43210",
        filedDate: "14 Feb 2026",
        status: "Under Review",
        daysPending: 12,
        escalated: false,
        escalationId: null
    };

    function getAllGrievances() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY_GRIEVANCES);
            let list = raw ? JSON.parse(raw) : [];
            if (!Array.isArray(list)) list = [];
            if (!list.some(g => g.id === defaultDemoGrievance.id)) {
                list.unshift(defaultDemoGrievance);
            }
            return list;
        } catch (e) {
            return [defaultDemoGrievance];
        }
    }

    function saveGrievance(record) {
        const list = getAllGrievances();
        const index = list.findIndex(g => g.id === record.id);
        if (index >= 0) {
            list[index] = record;
        } else {
            list.unshift(record);
        }
        localStorage.setItem(STORAGE_KEY_GRIEVANCES, JSON.stringify(list));
        updateGrievanceDrawerUI();
    }

    function findGrievance(idQuery) {
        if (!idQuery) return null;
        const normalized = idQuery.trim().toUpperCase();
        const list = getAllGrievances();
        return list.find(g => g.id.toUpperCase() === normalized || g.id.toUpperCase().replace(/-/g, '') === normalized.replace(/-/g, '')) || null;
    }

    // ==========================================================================
    // 4. Toast Notification System
    // ==========================================================================
    function showToast(title, message, type = "info", duration = 3500) {
        let container = document.getElementById("toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "toast-container";
            container.className = "toast-container";
            container.setAttribute("aria-live", "polite");
            document.body.appendChild(container);
        }

        const toast = document.createElement("div");
        toast.className = `toast toast--${type}`;
        const icons = {
            success: "✅",
            info: "ℹ️",
            warning: "⚠️",
            error: "❌"
        };

        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || "ℹ️"}</span>
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                <div class="toast-message">${message}</div>
            </div>
            <button type="button" class="toast-close" aria-label="Close notification">&times;</button>
        `;

        container.appendChild(toast);

        const closeBtn = toast.querySelector(".toast-close");
        function dismiss() {
            toast.classList.add("toast--leaving");
            setTimeout(() => {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 250);
        }

        closeBtn.addEventListener("click", dismiss);
        setTimeout(dismiss, duration);
    }

    // ==========================================================================
    // 5. Accessibility & Theme Engine (A-/A/A+, High Contrast, Dark Mode)
    // ==========================================================================
    function initAccessibility() {
        const root = document.documentElement;

        const savedFontSize = localStorage.getItem(STORAGE_KEY_FONT_SIZE);
        if (savedFontSize === "sm") {
            root.classList.add("font-size-sm");
        } else if (savedFontSize === "lg") {
            root.classList.add("font-size-lg");
        }

        const savedContrast = localStorage.getItem(STORAGE_KEY_CONTRAST);
        if (savedContrast === "high") {
            root.classList.add("high-contrast");
        }

        const savedTheme = localStorage.getItem(STORAGE_KEY_THEME);
        if (savedTheme === "dark") {
            root.classList.add("theme-dark");
            updateThemeButtonText(true);
        }

        document.querySelectorAll("[aria-label*='Decrease text size'], [aria-label*='Decrease font size'], #btn-text-decrease").forEach(btn => {
            btn.addEventListener("click", () => {
                root.classList.remove("font-size-lg");
                root.classList.add("font-size-sm");
                localStorage.setItem(STORAGE_KEY_FONT_SIZE, "sm");
                showToast("Font Size", "Text scale set to Small (14px)", "info", 2000);
            });
        });

        document.querySelectorAll("[aria-label*='Normal text size'], [aria-label*='Normal font size'], [aria-label*='Reset text size'], #btn-text-reset").forEach(btn => {
            btn.addEventListener("click", () => {
                root.classList.remove("font-size-sm", "font-size-lg");
                localStorage.setItem(STORAGE_KEY_FONT_SIZE, "md");
                showToast("Font Size", "Text scale reset to Default (16px)", "info", 2000);
            });
        });

        document.querySelectorAll("[aria-label*='Increase text size'], [aria-label*='Increase font size'], #btn-text-increase").forEach(btn => {
            btn.addEventListener("click", () => {
                root.classList.remove("font-size-sm");
                root.classList.add("font-size-lg");
                localStorage.setItem(STORAGE_KEY_FONT_SIZE, "lg");
                showToast("Font Size", "Text scale set to Large (18.5px)", "info", 2000);
            });
        });

        document.querySelectorAll("[aria-label*='High contrast'], [aria-label*='Toggle high contrast'], #btn-contrast-toggle").forEach(btn => {
            btn.addEventListener("click", () => {
                root.classList.toggle("high-contrast");
                const isHigh = root.classList.contains("high-contrast");
                localStorage.setItem(STORAGE_KEY_CONTRAST, isHigh ? "high" : "normal");
                showToast("High Contrast", isHigh ? "High contrast mode enabled" : "High contrast mode disabled", "info", 2000);
            });
        });

        document.querySelectorAll("#btn-theme-toggle, [aria-label*='Toggle Dark Mode']").forEach(btn => {
            btn.addEventListener("click", () => {
                root.classList.toggle("theme-dark");
                const isDark = root.classList.contains("theme-dark");
                localStorage.setItem(STORAGE_KEY_THEME, isDark ? "dark" : "light");
                updateThemeButtonText(isDark);
                showToast("Theme Updated", isDark ? "🌙 Dark mode activated" : "☀️ Light mode activated", "info", 2000);
            });
        });
    }

    function updateThemeButtonText(isDark) {
        document.querySelectorAll("#btn-theme-toggle, [aria-label*='Toggle Dark Mode']").forEach(btn => {
            btn.innerHTML = isDark ? "☀️ Light" : "🌙 Dark";
        });
    }

    // ==========================================================================
    // 6. Universal All-Indian-Language Translation Engine
    // ==========================================================================
    function triggerUniversalTranslate(lang) {
        if (!lang) lang = "en";
        
        // Handle cookie for persistent translation
        document.cookie = `googtrans=/en/${lang}; path=/;`;
        try {
            document.cookie = `googtrans=/en/${lang}; path=/; domain=${window.location.hostname};`;
        } catch (e) {}

        const selectEl = document.querySelector('.goog-te-combo');
        if (selectEl) {
            selectEl.value = lang;
            selectEl.dispatchEvent(new Event('change'));
        }
    }

    function setLanguage(lang) {
        if (!languageNames[lang]) lang = "en";
        localStorage.setItem(STORAGE_KEY_LANG, lang);
        document.documentElement.lang = lang;

        // Set RTL for Urdu, Sindhi, Kashmiri
        if (lang === "ur" || lang === "sd" || lang === "ks") {
            document.documentElement.setAttribute("dir", "rtl");
        } else {
            document.documentElement.setAttribute("dir", "ltr");
        }

        // Synchronize all select elements on the page
        document.querySelectorAll(".lang-select, #lang-select, #lang-selector, .gov-tools select").forEach(sel => {
            sel.value = lang;
        });

        // Translate text elements with data-i18n
        const dict = i18nData[lang] || i18nData["en"];
        document.querySelectorAll("[data-i18n]").forEach(el => {
            const key = el.getAttribute("data-i18n");
            if (dict && dict[key]) {
                el.textContent = dict[key];
            } else if (i18nData.en[key]) {
                el.textContent = i18nData.en[key];
            }
        });

        // Update Sahayak assistant elements
        const sahayakGreeting = document.getElementById("sahayak-greeting-msg");
        if (sahayakGreeting && dict && dict.sahayak_greeting) {
            sahayakGreeting.innerHTML = dict.sahayak_greeting;
        }
        const sahayakTitle = document.getElementById("sahayak-title");
        if (sahayakTitle && dict && dict.sahayak_title) {
            sahayakTitle.textContent = dict.sahayak_title;
        }
        const sahayakInput = document.getElementById("sahayak-input");
        if (sahayakInput && dict && dict.sahayak_placeholder) {
            sahayakInput.placeholder = dict.sahayak_placeholder;
        }

        // Trigger Universal Web Translate
        triggerUniversalTranslate(lang);
    }

    function loadUniversalTranslateScript() {
        if (document.getElementById("google-translate-script")) return;

        window.googleTranslateElementInit = function () {
            try {
                if (window.google && window.google.translate) {
                    new window.google.translate.TranslateElement({
                        pageLanguage: 'en',
                        includedLanguages: 'en,hi,bn,ta,te,mr,gu,kn,ml,pa,or,as,ur,sa,mai,doi,kok,ne,sd,ks,sat,brx,mni',
                        autoDisplay: false
                    }, 'google_translate_element');

                    const savedLang = localStorage.getItem(STORAGE_KEY_LANG);
                    if (savedLang && savedLang !== 'en') {
                        setTimeout(() => triggerUniversalTranslate(savedLang), 400);
                    }
                }
            } catch (e) {}
        };

        const s = document.createElement("script");
        s.id = "google-translate-script";
        s.src = "https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit";
        s.async = true;
        document.head.appendChild(s);
    }

    function initLanguageToggle() {
        const savedLang = localStorage.getItem(STORAGE_KEY_LANG) || "en";
        document.querySelectorAll(".lang-select, #lang-select, #lang-selector, .gov-tools select").forEach(sel => {
            sel.value = savedLang;
            sel.addEventListener("change", (e) => {
                const newLang = e.target.value;
                setLanguage(newLang);
                showToast("Language Selected", `Website translated to ${languageNames[newLang] || newLang}.`, "info", 2500);
            });
        });
        setLanguage(savedLang);
        loadUniversalTranslateScript();
    }

    // ==========================================================================
    // 6.5 IBM Db2 Backend API Connector
    // ==========================================================================
    async function apiRequest(endpoint, options = {}) {
        const defaultHeaders = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        };
        options.headers = { ...defaultHeaders, ...options.headers };

        // Attempt relative /api first (works seamlessly via Docker Nginx reverse proxy)
        try {
            const res = await fetch(`/api${endpoint}`, options);
            if (res.status !== 502 && res.status !== 503) {
                if (res.status === 404 && !endpoint.startsWith("/grievances/")) {
                    // Not a backend endpoint
                } else {
                    return res;
                }
            }
        } catch (err) {
            // Relative URL network failure, will try direct port 8000 fallback
        }

        // Direct fallback to http://localhost:8000/api for local/standalone viewing
        try {
            return await fetch(`http://localhost:8000/api${endpoint}`, options);
        } catch (fallbackErr) {
            console.error("API request failed on both relative /api and localhost:8000/api", fallbackErr);
            throw fallbackErr;
        }
    }

    // ==========================================================================
    // 7. Lodge Grievance Wizard (Voice, Keywords, GPS, Photo Previews & ID Gen)
    // ==========================================================================
    function initLodgeGrievancePage() {
        const descInput = document.getElementById("description");
        const subjectInput = document.getElementById("subject");
        const deptSelect = document.getElementById("department");
        const voiceBtn = document.getElementById("btn-voice-input");
        const voiceBanner = document.getElementById("voice-status-banner");
        const suggestedDeptBox = document.getElementById("suggested-dept-box");
        const suggestedDeptText = document.getElementById("suggested-dept-text");
        const btnApplySuggestion = document.getElementById("btn-apply-suggestion");
        const grievanceForm = document.getElementById("grievanceForm");
        const submitBtn = document.getElementById("btn-submit");
        const btnDetectGps = document.getElementById("btn-detect-gps");
        const gpsStatusText = document.getElementById("gps-status-text");
        const documentsInput = document.getElementById("documents");
        const photoPreviewGrid = document.getElementById("photo-preview-grid");
        const dropZone = document.getElementById("drop-zone");

        if (!descInput && !grievanceForm) return;

        let detectedDept = null;
        let activeRecognition = null;
        let uploadedFiles = [];

        // --- A. Keyword Matcher for Suggested Department ---
        function checkKeywords() {
            const text = ((subjectInput ? subjectInput.value : "") + " " + (descInput ? descInput.value : "")).toLowerCase();
            if (text.length < 3) {
                if (suggestedDeptBox) suggestedDeptBox.classList.remove("active");
                detectedDept = null;
                return;
            }

            let bestMatch = null;
            for (const rule of deptKeywordRules) {
                for (const kw of rule.keywords) {
                    if (text.includes(kw.toLowerCase())) {
                        bestMatch = rule;
                        break;
                    }
                }
                if (bestMatch) break;
            }

            if (bestMatch && suggestedDeptBox && suggestedDeptText) {
                detectedDept = bestMatch;
                const currentLang = localStorage.getItem(STORAGE_KEY_LANG) || "en";
                suggestedDeptText.textContent = currentLang === "hi" ? bestMatch.deptNameHi : bestMatch.deptName;
                suggestedDeptBox.classList.add("active");
            } else if (suggestedDeptBox) {
                suggestedDeptBox.classList.remove("active");
                detectedDept = null;
            }
        }

        if (descInput) descInput.addEventListener("input", checkKeywords);
        if (subjectInput) subjectInput.addEventListener("input", checkKeywords);

        // --- B. Apply Suggested Department ---
        if (btnApplySuggestion && deptSelect) {
            btnApplySuggestion.addEventListener("click", () => {
                if (!detectedDept) return;
                let optionExists = false;
                for (let i = 0; i < deptSelect.options.length; i++) {
                    if (deptSelect.options[i].value === detectedDept.deptCode || deptSelect.options[i].text.toLowerCase().includes(detectedDept.deptCode)) {
                        deptSelect.selectedIndex = i;
                        optionExists = true;
                        break;
                    }
                }
                if (!optionExists) {
                    const opt = document.createElement("option");
                    opt.value = detectedDept.deptCode;
                    opt.textContent = detectedDept.deptName;
                    opt.selected = true;
                    deptSelect.appendChild(opt);
                }

                showToast("Department Assigned", `Assigned to: ${detectedDept.deptName}`, "success");

                btnApplySuggestion.textContent = "✓ Assigned!";
                btnApplySuggestion.style.backgroundColor = "var(--color-success)";
                setTimeout(() => {
                    const currentLang = localStorage.getItem(STORAGE_KEY_LANG) || "en";
                    const dict = i18nData[currentLang] || i18nData["en"];
                    btnApplySuggestion.textContent = dict.btn_apply_suggestion || "Apply Suggestion";
                    btnApplySuggestion.style.backgroundColor = "";
                    if (suggestedDeptBox) suggestedDeptBox.classList.remove("active");
                }, 1400);
            });
        }

        // --- C. Real Web Speech Recognition with All-Indian-Dialect Mapping ---
        if (voiceBtn) {
            const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;

            voiceBtn.addEventListener("click", () => {
                const isListening = voiceBtn.classList.contains("listening");

                if (isListening) {
                    if (activeRecognition) {
                        activeRecognition.stop();
                        activeRecognition = null;
                    }
                    stopListeningUI();
                    return;
                }

                startListeningUI();

                if (SpeechRec) {
                    try {
                        const rec = new SpeechRec();
                        rec.continuous = true;
                        rec.interimResults = true;
                        const currentLang = localStorage.getItem(STORAGE_KEY_LANG) || "en";
                        rec.lang = voiceLocaleMap[currentLang] || "en-IN";

                        let basePrefix = "";

                        rec.onstart = () => {
                            if (descInput) {
                                basePrefix = descInput.value.trim();
                            }
                            showToast("🎙️ Voice Active", `Speak now in ${languageNames[currentLang] || 'your language'}...`, "info", 2500);
                        };

                        rec.onresult = (e) => {
                            let finalTranscript = "";
                            let interimTranscript = "";
                            for (let i = 0; i < e.results.length; ++i) {
                                const transcript = e.results[i][0].transcript;
                                if (e.results[i].isFinal) {
                                    finalTranscript += (finalTranscript ? " " : "") + transcript.trim();
                                } else {
                                    interimTranscript += (interimTranscript ? " " : "") + transcript.trim();
                                }
                            }

                            // Cleanly combine prefix + final + interim without duplicating text
                            const parts = [];
                            if (basePrefix) parts.push(basePrefix);
                            if (finalTranscript) parts.push(finalTranscript);
                            if (interimTranscript) parts.push(interimTranscript);
                            const currentCombined = parts.join(" ");

                            if (descInput) {
                                descInput.value = currentCombined;
                                const counter = document.getElementById("desc-counter");
                                if (counter) counter.textContent = `${descInput.value.length} / 3000`;
                            }

                            // Auto subject if empty
                            if (subjectInput && !subjectInput.value && currentCombined.length > 5) {
                                const words = currentCombined.split(" ").slice(0, 7).join(" ");
                                subjectInput.value = words.charAt(0).toUpperCase() + words.slice(1);
                            }

                            checkKeywords();
                        };

                        rec.onerror = (e) => {
                            console.warn("Speech recognition error:", e.error);
                            if (e.error !== "no-speech") {
                                triggerSimulatedVoiceFallback();
                            }
                        };

                        rec.onend = () => {
                            stopListeningUI();
                            activeRecognition = null;
                        };

                        activeRecognition = rec;
                        rec.start();
                    } catch (err) {
                        triggerSimulatedVoiceFallback();
                    }
                } else {
                    triggerSimulatedVoiceFallback();
                }
            });
        }

        function startListeningUI() {
            if (voiceBtn) {
                voiceBtn.classList.add("listening");
                voiceBtn.innerHTML = "<span>🔴 Listening... (Click to stop)</span>";
            }
            if (voiceBanner) voiceBanner.classList.add("active");
        }

        function stopListeningUI() {
            if (voiceBtn) {
                voiceBtn.classList.remove("listening");
                voiceBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg> Voice Input (Speak)`;
            }
            if (voiceBanner) voiceBanner.classList.remove("active");
        }

        function triggerSimulatedVoiceFallback() {
            showToast("🎙️ Voice Simulator", "Microphone access unavailable. Auto-filling realistic sample complaint.", "info", 3000);
            setTimeout(() => {
                stopListeningUI();
                const sample = sampleVoiceGrievances[Math.floor(Math.random() * sampleVoiceGrievances.length)];
                if (subjectInput && !subjectInput.value) {
                    subjectInput.value = sample.subject;
                }
                if (descInput) {
                    descInput.value = sample.description;
                    const counter = document.getElementById("desc-counter");
                    if (counter) counter.textContent = `${descInput.value.length} / 3000`;
                }
                const radio = document.querySelector(`input[name="issue_category"][value="${sample.category}"]`);
                if (radio) radio.checked = true;
                checkKeywords();
            }, 1800);
        }

        // --- D. 1-Click GPS Geolocation & Landmark Tagging ---
        if (btnDetectGps) {
            btnDetectGps.addEventListener("click", () => {
                btnDetectGps.innerHTML = `<span>🛰️ Locating...</span>`;

                if ("geolocation" in navigator) {
                    navigator.geolocation.getCurrentPosition(
                        (position) => {
                            const lat = position.coords.latitude.toFixed(4);
                            const lon = position.coords.longitude.toFixed(4);
                            const tag = `GPS Verified: ${lat}° N, ${lon}° E (Delhi NCT Region)`;
                            if (gpsStatusText) {
                                gpsStatusText.innerHTML = `<strong style="color: #15803d;">📍 ${tag}</strong>`;
                            }
                            const stateSelect = document.getElementById("state");
                            if (stateSelect && (!stateSelect.value || stateSelect.value === "other")) {
                                stateSelect.value = "delhi";
                            }
                            btnDetectGps.innerHTML = `<span>✓ Location Tagged</span>`;
                            btnDetectGps.style.background = "#15803d";
                            showToast("📍 Location Tagged", `GPS Coordinates (${lat}, ${lon}) successfully attached.`, "success");
                        },
                        () => {
                            const simTag = `Connaught Place, New Delhi - 110001 (Simulated GPS: 28.6328° N, 77.2197° E)`;
                            if (gpsStatusText) {
                                gpsStatusText.innerHTML = `<strong style="color: #15803d;">📍 ${simTag}</strong>`;
                            }
                            const stateSelect = document.getElementById("state");
                            if (stateSelect) stateSelect.value = "delhi";
                            btnDetectGps.innerHTML = `<span>✓ Location Tagged</span>`;
                            showToast("📍 Location Tagged", "Location attached: New Delhi (NCT)", "success");
                        },
                        { timeout: 4000 }
                    );
                } else {
                    if (gpsStatusText) {
                        gpsStatusText.innerHTML = `<strong style="color: #15803d;">📍 New Delhi (NCT Region Tagged)</strong>`;
                    }
                    btnDetectGps.innerHTML = `<span>✓ Location Tagged</span>`;
                    showToast("📍 Location Tagged", "Location attached: New Delhi (NCT)", "success");
                }
            });
        }

        // --- E. Photo / Document Upload with Image Previews & Removal ---
        function renderFileThumbnails(files) {
            if (!photoPreviewGrid) return;
            photoPreviewGrid.innerHTML = "";

            uploadedFiles = Array.from(files);

            uploadedFiles.forEach((file, idx) => {
                const card = document.createElement("div");
                card.className = "photo-card";

                if (file.type.startsWith("image/")) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        card.innerHTML = `
                            <img src="${e.target.result}" alt="${file.name}">
                            <button type="button" class="photo-card-remove" data-index="${idx}" title="Remove file">✕</button>
                            <div class="photo-card-name">${file.name}</div>
                        `;
                        attachRemoveHandler(card, idx);
                    };
                    reader.readAsDataURL(file);
                } else {
                    card.innerHTML = `
                        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; padding: 10px; background: #e0f2fe; color: #0369a1;">
                            <span style="font-size: 1.75rem;">📄</span>
                            <span style="font-size: 0.6875rem; font-weight: 700; margin-top: 4px;">PDF DOCUMENT</span>
                        </div>
                        <button type="button" class="photo-card-remove" data-index="${idx}" title="Remove file">✕</button>
                        <div class="photo-card-name">${file.name}</div>
                    `;
                    attachRemoveHandler(card, idx);
                }

                photoPreviewGrid.appendChild(card);
            });

            if (uploadedFiles.length > 0) {
                showToast("📁 Documents Attached", `${uploadedFiles.length} file(s) added successfully.`, "info", 2000);
            }
        }

        function attachRemoveHandler(card, index) {
            const removeBtn = card.querySelector(".photo-card-remove");
            if (removeBtn) {
                removeBtn.addEventListener("click", () => {
                    uploadedFiles.splice(index, 1);
                    card.remove();
                    showToast("File Removed", "Supporting document removed", "info", 1500);
                });
            }
        }

        if (documentsInput) {
            documentsInput.addEventListener("change", (e) => {
                if (e.target.files && e.target.files.length > 0) {
                    renderFileThumbnails(e.target.files);
                }
            });
        }

        if (dropZone && documentsInput) {
            dropZone.addEventListener("click", () => documentsInput.click());
            dropZone.addEventListener("dragover", (e) => {
                e.preventDefault();
                dropZone.style.borderColor = "var(--color-navy)";
            });
            dropZone.addEventListener("dragleave", () => {
                dropZone.style.borderColor = "";
            });
            dropZone.addEventListener("drop", (e) => {
                e.preventDefault();
                dropZone.style.borderColor = "";
                if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                    renderFileThumbnails(e.dataTransfer.files);
                }
            });
        }

        // --- F. Form Submission & IBM Db2 API Integration ---
        if (submitBtn) {
            submitBtn.addEventListener("click", async () => {
                const consent = document.getElementById("consent");
                if (consent && !consent.checked) {
                    showToast("Consent Required", "Please confirm that the information provided is accurate.", "warning");
                    return;
                }

                const descVal = descInput ? descInput.value.trim() : "";
                if (descVal.length < 10) {
                    showToast("Description Required", "Please enter a detailed description (minimum 10 characters).", "warning");
                    return;
                }

                const subjectVal = subjectInput && subjectInput.value ? subjectInput.value.trim() : "Public Grievance";
                const nameVal = document.getElementById("fullname") ? document.getElementById("fullname").value.trim() : "Citizen";
                const emailVal = document.getElementById("email") ? document.getElementById("email").value.trim() : "";
                const mobileVal = document.getElementById("mobile") ? document.getElementById("mobile").value.trim() : "";
                const contactVal = [mobileVal, emailVal].filter(Boolean).join(" / ") || "Not Provided";
                
                const addressVal = document.getElementById("address") ? document.getElementById("address").value.trim() : "";
                const wardVal = addressVal ? addressVal.slice(0, 100) : "Ward 14 - Rohini East";
                const stateSelect = document.getElementById("state");
                const stateVal = stateSelect && stateSelect.selectedIndex >= 0 ? stateSelect.options[stateSelect.selectedIndex].text : "Delhi (NCT)";
                const pincodeVal = document.getElementById("pincode") ? document.getElementById("pincode").value.trim() : "110001";

                // Determine category
                let categoryVal = "water";
                const checkedRadio = document.querySelector('input[name="issue_category"]:checked');
                const deptVal = deptSelect && deptSelect.selectedIndex > 0 ? deptSelect.value : "";
                
                if (["water", "electricity", "road", "roads", "sanitation", "health", "food", "pension"].includes(deptVal)) {
                    categoryVal = deptVal === "road" ? "roads" : deptVal;
                } else if (checkedRadio) {
                    const radioVal = checkedRadio.value;
                    const catMap = {
                        "delay": "water",
                        "conduct": "sanitation",
                        "scheme": "pension",
                        "psu": "electricity",
                        "corruption": "roads",
                        "other": "health"
                    };
                    categoryVal = catMap[radioVal] || "water";
                }

                // Show Loading State
                const originalHtml = submitBtn.innerHTML;
                submitBtn.disabled = true;
                submitBtn.innerHTML = `<span>⏳ Submitting to IBM Db2...</span>`;
                
                const errorBanner = document.getElementById("submit-error-banner");
                if (errorBanner) errorBanner.remove();

                try {
                    const payload = {
                        citizen_name: nameVal,
                        contact: contactVal,
                        category: categoryVal,
                        subject: subjectVal,
                        description: descVal,
                        ward: wardVal,
                        priority: "Medium",
                        state: stateVal,
                        pincode: pincodeVal
                    };

                    const response = await apiRequest("/grievances", {
                        method: "POST",
                        body: JSON.stringify(payload)
                    });

                    if (!response.ok) {
                        const errData = await response.json().catch(() => ({}));
                        throw new Error(errData.detail || `Server returned HTTP ${response.status}`);
                    }

                    const resData = await response.json();
                    const trackingId = resData.tracking_id || resData.data?.tracking_id;

                    // Also cache for session drawer
                    saveGrievance({
                        id: trackingId,
                        subject: subjectVal,
                        description: descVal,
                        department: deptSelect && deptSelect.selectedIndex > 0 ? deptSelect.options[deptSelect.selectedIndex].text : "Concerned Department",
                        category: categoryVal,
                        name: nameVal,
                        email: emailVal,
                        mobile: mobileVal,
                        filedDate: new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }),
                        status: "Filed",
                        daysPending: 0,
                        escalated: false
                    });

                    // Update UI elements with confirmed tracking ID
                    document.querySelectorAll(".reg-value").forEach(el => el.textContent = trackingId);
                    const trackLink = document.querySelector("#step-confirmation a[href*='track-status']");
                    if (trackLink) {
                        trackLink.href = `track-status.html?id=${trackingId}`;
                    }

                    // Populate AI Triage box
                    if (resData.ai_triage) {
                        const aiCat = document.getElementById("conf-ai-category");
                        const aiPri = document.getElementById("conf-ai-priority");
                        const aiSum = document.getElementById("conf-ai-summary");
                        const aiMethod = document.getElementById("conf-ai-method");

                        if (aiCat) aiCat.textContent = resData.ai_triage.category;
                        if (aiPri) {
                            aiPri.textContent = resData.ai_triage.priority;
                            aiPri.style.color = resData.ai_triage.priority === "Critical" ? "#dc2626" : (resData.ai_triage.priority === "High" ? "#d97706" : "#2563eb");
                        }
                        if (aiSum) aiSum.textContent = resData.ai_triage.summary;
                        if (aiMethod) aiMethod.textContent = resData.ai_triage.method === "langchain_llm" ? "LangChain LLM Chain" : "Rule-Based AI Classifier";
                    }

                    // Populate Hotspot / Duplicate box
                    const hotspotBox = document.getElementById("conf-hotspot-box");
                    if (hotspotBox && resData.hotspot_alert && resData.hotspot_alert.is_hotspot) {
                        hotspotBox.style.display = "block";
                        const msgEl = document.getElementById("conf-hotspot-msg");
                        if (msgEl) msgEl.textContent = resData.hotspot_alert.message;

                        const dupsList = document.getElementById("conf-duplicates-list");
                        if (dupsList) {
                            dupsList.innerHTML = "";
                            if (resData.potential_duplicates && resData.potential_duplicates.length > 0) {
                                let html = `<strong style="display:block; margin-top:0.35rem; color:#78350f;">Potential Overlapping Dockets in Db2:</strong><ul style="margin:0.25rem 0 0 1rem; padding:0;">`;
                                resData.potential_duplicates.forEach(dup => {
                                    html += `<li><a href="track-status.html?id=${dup.tracking_id}" style="color:#b45309; text-decoration:underline; font-weight:600;">${dup.tracking_id}</a> - ${dup.subject || 'Similar complaint'} (${dup.status})</li>`;
                                });
                                html += `</ul>`;
                                dupsList.innerHTML = html;
                            }
                        }
                    } else if (hotspotBox) {
                        hotspotBox.style.display = "none";
                    }

                    showToast("Grievance Lodged in IBM Db2!", `Assigned Tracking ID: ${trackingId}`, "success", 6000);

                    // Transition to confirmation step
                    if (window.updateGrievanceView) {
                        window.updateGrievanceView("confirmation");
                    } else {
                        document.querySelectorAll('.form-step').forEach(el => el.classList.add('hidden'));
                        document.getElementById('step-confirmation')?.classList.remove('hidden');
                        document.querySelector('.stepper')?.classList.add('hidden');
                        window.scrollTo(0, 0);
                    }
                } catch (error) {
                    console.error("Grievance submission error:", error);
                    showToast("Submission Failed", "Could not submit to IBM Db2 backend. Please check connection and try again.", "error", 5000);

                    // Add visible error banner in step 5
                    const step5 = document.getElementById("step-5");
                    if (step5) {
                        const banner = document.createElement("div");
                        banner.id = "submit-error-banner";
                        banner.className = "alert alert--danger";
                        banner.style.marginTop = "1rem";
                        banner.style.borderLeft = "4px solid #dc2626";
                        banner.style.backgroundColor = "#fef2f2";
                        banner.style.color = "#991b1b";
                        banner.style.padding = "0.875rem 1rem";
                        banner.style.borderRadius = "6px";
                        banner.innerHTML = `
                            <strong>⚠️ Submission Error:</strong> Could not connect to the IBM Db2 backend API (${error.message}). Please ensure backend service is running.
                        `;
                        const actions = step5.querySelector(".form-actions");
                        if (actions) {
                            step5.insertBefore(banner, actions);
                        } else {
                            step5.appendChild(banner);
                        }
                    }
                } finally {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalHtml;
                }
            });
        }
    }

    // ==========================================================================
    // 8. Track Status & 4-Stage Timeline & Escalation Module
    // ==========================================================================
    function initTrackStatusPage() {
        const trackForm = document.getElementById("track-form");
        const searchSection = document.getElementById("search-section");
        const statusResult = document.getElementById("status-result");
        const statusError = document.getElementById("status-error");
        const regInput = document.getElementById("reg-number");
        const displayRegNum = document.getElementById("display-reg-num");
        const escalateBtn = document.getElementById("btn-escalate");
        const escalateCard = document.getElementById("escalation-card");
        const escalateModal = document.getElementById("escalate-modal");
        const btnConfirmEscalate = document.getElementById("btn-confirm-escalate");
        const btnCancelEscalate = document.getElementById("btn-cancel-escalate");

        if (!trackForm && !statusResult) return;

        let activeGrievance = null;

        function renderGrievance(grievance) {
            activeGrievance = grievance;
            if (searchSection) searchSection.style.display = "none";
            if (statusError) statusError.style.display = "none";
            if (statusResult) statusResult.style.display = "block";

            const trackingId = grievance.tracking_id || grievance.id;
            if (displayRegNum) displayRegNum.textContent = trackingId;

            // Format date
            let formattedDate = "Recent";
            if (grievance.created_at) {
                try {
                    formattedDate = new Date(grievance.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
                } catch(e) {
                    formattedDate = grievance.created_at;
                }
            } else if (grievance.filedDate) {
                formattedDate = grievance.filedDate;
            }

            const submittedEl = document.getElementById("meta-submitted");
            if (submittedEl) submittedEl.textContent = formattedDate;

            const deptEl = document.getElementById("meta-dept");
            if (deptEl) deptEl.textContent = grievance.department_name || grievance.department || grievance.ward || "Concerned Department";

            const catEl = document.getElementById("meta-cat");
            if (catEl) {
                const catStr = grievance.category || "General";
                catEl.textContent = catStr.charAt(0).toUpperCase() + catStr.slice(1);
            }

            // Status Badge
            const statusBadge = document.getElementById("status-badge");
            if (statusBadge) {
                const st = (grievance.status || "Filed").toLowerCase();
                const prio = (grievance.priority || "").toLowerCase();

                if (prio === "critical" || grievance.escalated) {
                    statusBadge.className = "status-badge status-badge--escalated";
                    statusBadge.innerHTML = "<span>🚨</span> Escalated - Priority Review";
                } else if (st === "resolved") {
                    statusBadge.className = "status-badge status-badge--resolved";
                    statusBadge.innerHTML = "<span>✅</span> Resolved";
                    statusBadge.style.backgroundColor = "#dcfce7";
                    statusBadge.style.color = "#15803d";
                } else if (st === "forwarded to dept") {
                    statusBadge.className = "status-badge status-badge--forwarded";
                    statusBadge.innerHTML = "<span>📤</span> Forwarded to Dept";
                    statusBadge.style.backgroundColor = "#e0f2fe";
                    statusBadge.style.color = "#0369a1";
                } else {
                    statusBadge.className = "status-badge status-badge--review";
                    statusBadge.innerHTML = "<span>⏳</span> " + (grievance.status || "Under Review");
                }
            }

            // Update latest note alert
            const alertNote = document.querySelector("#status-result .alert--info strong");
            if (alertNote && alertNote.parentElement) {
                if (grievance.updates && grievance.updates.length > 0) {
                    // Prioritize operational human/officer updates over raw kernel trigger telemetry
                    const humanUpdates = grievance.updates.filter(u => u.updated_by && !u.updated_by.includes("TRG_AUDIT"));
                    const latest = humanUpdates.length > 0 ? humanUpdates[humanUpdates.length - 1] : grievance.updates[grievance.updates.length - 1];
                    alertNote.parentElement.innerHTML = `
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="alert-icon"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                        <div>
                            <strong>Latest Officer Note (${latest.updated_by}):</strong> ${latest.notes || "Grievance status updated in IBM Db2."}
                        </div>
                    `;
                }
            }

            render4StageTimeline(grievance);

            // Escalation card display
            if (escalateCard) {
                const isCrit = (grievance.priority || "").toLowerCase() === "critical" || grievance.escalated;
                const isRes = (grievance.status || "").toLowerCase() === "resolved";

                if (isCrit) {
                    escalateCard.style.display = "flex";
                    escalateCard.innerHTML = `
                        <div class="escalation-content">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#15803d" stroke-width="2" class="escalation-icon"><circle cx="12" cy="12" r="10"/><polyline points="20 6 9 17 4 12"/></svg>
                            <div>
                                <h4 class="escalation-title" style="color: #15803d;">Grievance Escalated in IBM Db2</h4>
                                <p class="escalation-text" style="color: #166534;">Your grievance is currently marked as <strong>High / Critical Priority</strong> and forwarded to the Appellate Nodal Officer for urgent disposal.</p>
                            </div>
                        </div>
                    `;
                    escalateCard.style.borderColor = "#86efac";
                    escalateCard.style.background = "#f0fdf4";
                } else if (isRes) {
                    escalateCard.style.display = "none";
                } else {
                    escalateCard.style.display = "flex";
                }
            }

            // Update IBM Db2 Citizen Charter SLA countdown bar
            const createdDate = new Date(grievance.created_at || Date.now());
            const now = new Date();
            const diffDays = Math.max(0, Math.floor((now - createdDate) / (1000 * 60 * 60 * 24)));
            const daysOpen = (grievance.days_open !== undefined && grievance.days_open !== null) ? Number(grievance.days_open) : diffDays;
            const isResolved = (grievance.status || "").toLowerCase() === "resolved";
            if (typeof window.updateSLABar === "function") {
                window.updateSLABar(daysOpen, isResolved);
            }
        }

        function render4StageTimeline(grievance) {
            const timelineContainer = document.getElementById("timeline-container");
            if (!timelineContainer) return;

            const st = (grievance.status || "Filed").toLowerCase();
            const isEscalated = (grievance.priority || "").toLowerCase() === "critical" || grievance.escalated;

            // Map updates to stages
            const updates = grievance.updates || [];
            const filedUpd = updates.find(u => (u.new_status || "").toLowerCase() === "filed") || updates[0];
            const reviewUpd = updates.find(u => (u.new_status || "").toLowerCase() === "under review");
            const fwdUpd = updates.find(u => (u.new_status || "").toLowerCase() === "forwarded to dept");
            const resUpd = updates.find(u => (u.new_status || "").toLowerCase() === "resolved");

            let progressBarWidth = "25%";
            let s1Class = "completed", s2Class = "pending", s3Class = "pending", s4Class = "pending";

            if (st === "resolved") {
                progressBarWidth = "100%";
                s1Class = "completed"; s2Class = "completed"; s3Class = "completed"; s4Class = "completed";
            } else if (st === "forwarded to dept") {
                progressBarWidth = "75%";
                s1Class = "completed"; s2Class = "completed"; s3Class = "current"; s4Class = "pending";
            } else if (st === "under review") {
                progressBarWidth = "50%";
                s1Class = "completed"; s2Class = "current"; s3Class = "pending"; s4Class = "pending";
            } else {
                progressBarWidth = "25%";
                s1Class = "current"; s2Class = "pending"; s3Class = "pending"; s4Class = "pending";
            }

            const formatDate = (isoStr) => {
                if (!isoStr) return "";
                try {
                    return new Date(isoStr).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
                } catch(e) {
                    return isoStr;
                }
            };

            const filedDateStr = formatDate(filedUpd?.created_at || grievance.created_at) || "Filed";
            const reviewDateStr = reviewUpd ? formatDate(reviewUpd.created_at) : (isEscalated ? '<span style="color: #dc2626; font-weight: bold;">[Escalated Priority]</span>' : 'Pending Review');
            const fwdDateStr = fwdUpd ? formatDate(fwdUpd.created_at) : (s3Class === "current" ? "Field Inspection" : "Next Stage");
            const resDateStr = resUpd ? formatDate(resUpd.created_at) : (st === "resolved" ? "Completed" : "Target 30 Days");

            timelineContainer.innerHTML = `
                <div class="timeline-4stage">
                    <div class="timeline-progress-bar" style="width: ${progressBarWidth};"></div>
                    
                    <!-- Stage 1: Filed -->
                    <div class="stage-item ${s1Class}">
                        <div class="stage-node">✓</div>
                        <h4 class="stage-title" data-i18n="stage_filed">Filed</h4>
                        <p class="stage-desc">${filedDateStr}</p>
                    </div>

                    <!-- Stage 2: Under Review -->
                    <div class="stage-item ${s2Class}">
                        <div class="stage-node">${s2Class === "completed" ? "✓" : "2"}</div>
                        <h4 class="stage-title" data-i18n="stage_review">Under Review</h4>
                        <p class="stage-desc">${reviewDateStr}</p>
                    </div>

                    <!-- Stage 3: Forwarded to Dept -->
                    <div class="stage-item ${s3Class}">
                        <div class="stage-node">${s3Class === "completed" ? "✓" : "3"}</div>
                        <h4 class="stage-title" data-i18n="stage_forwarded">Forwarded to Dept</h4>
                        <p class="stage-desc">${fwdDateStr}</p>
                    </div>

                    <!-- Stage 4: Resolved -->
                    <div class="stage-item ${s4Class}">
                        <div class="stage-node">${s4Class === "completed" ? "✓" : "4"}</div>
                        <h4 class="stage-title" data-i18n="stage_resolved">Resolved</h4>
                        <p class="stage-desc">${resDateStr}</p>
                    </div>
                </div>
            `;
        }

        async function fetchAndRenderGrievance(queryId) {
            if (!queryId) return;
            const cleanId = queryId.trim().toUpperCase();

            // Loading state
            const submitBtn = trackForm ? trackForm.querySelector("button[type='submit']") : null;
            const originalBtnText = submitBtn ? submitBtn.innerHTML : "";
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = `<span>🔍 Querying IBM Db2...</span>`;
            }

            try {
                const response = await apiRequest(`/grievances/${encodeURIComponent(cleanId)}`);

                if (response.ok) {
                    const resJson = await response.json();
                    if (resJson.data) {
                        renderGrievance(resJson.data);
                        showToast("Record Retrieved from IBM Db2", `Status loaded for ${resJson.data.tracking_id}`, "success", 2500);
                        return;
                    }
                }

                // If not found in API, check local fallback or show error
                if (response.status === 404) {
                    const localFallback = findGrievance(cleanId);
                    if (localFallback) {
                        renderGrievance(localFallback);
                        showToast("Cached Record Loaded", `Loaded session data for ${cleanId}`, "info", 2500);
                        return;
                    }
                }

                // Not found error
                if (searchSection) searchSection.style.display = "none";
                if (statusResult) statusResult.style.display = "none";
                if (statusError) {
                    statusError.style.display = "block";
                    const errText = statusError.querySelector(".card p");
                    if (errText) {
                        errText.textContent = `We could not find an active grievance matching "${cleanId}" in IBM Db2. Please check the registration number.`;
                    }
                }
                showToast("No Record Found", `No grievance matching "${cleanId}" in IBM Db2`, "error", 3500);
            } catch (err) {
                console.error("Error fetching grievance from Db2:", err);
                const localFallback = findGrievance(cleanId);
                if (localFallback) {
                    renderGrievance(localFallback);
                    showToast("Offline Cache Loaded", `Backend unreachable; loaded cached ${cleanId}`, "warning", 3000);
                    return;
                }
                if (searchSection) searchSection.style.display = "none";
                if (statusResult) statusResult.style.display = "none";
                if (statusError) statusError.style.display = "block";
                showToast("Connection Error", "Could not reach IBM Db2 backend API.", "error", 4000);
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnText || "Track Status &rarr;";
                }
            }
        }

        if (trackForm) {
            trackForm.addEventListener("submit", (e) => {
                e.preventDefault();
                const query = regInput ? regInput.value.trim() : "";
                if (query) {
                    fetchAndRenderGrievance(query);
                }
            });
        }

        const urlParams = new URLSearchParams(window.location.search);
        const idFromUrl = urlParams.get("id") || urlParams.get("reg");
        if (idFromUrl) {
            if (regInput) regInput.value = idFromUrl;
            fetchAndRenderGrievance(idFromUrl);
        }

        const tryAgainBtn = document.getElementById("try-again-btn");
        if (tryAgainBtn) {
            tryAgainBtn.addEventListener("click", () => {
                if (statusError) statusError.style.display = "none";
                if (searchSection) searchSection.style.display = "block";
                if (regInput) {
                    regInput.value = "";
                    regInput.focus();
                }
            });
        }

        const searchAgainBtn = document.getElementById("search-again-btn");
        if (searchAgainBtn) {
            searchAgainBtn.addEventListener("click", () => {
                if (statusResult) statusResult.style.display = "none";
                if (searchSection) searchSection.style.display = "block";
                if (regInput) {
                    regInput.value = "";
                    regInput.focus();
                }
            });
        }

        if (escalateBtn) {
            escalateBtn.addEventListener("click", () => {
                if (escalateModal) {
                    escalateModal.classList.add("active");
                }
            });
        }

        if (btnCancelEscalate && escalateModal) {
            btnCancelEscalate.addEventListener("click", () => {
                escalateModal.classList.remove("active");
            });
        }

        if (btnConfirmEscalate && escalateModal) {
            btnConfirmEscalate.addEventListener("click", async () => {
                escalateModal.classList.remove("active");
                if (!activeGrievance) return;

                const trackingId = activeGrievance.tracking_id || activeGrievance.id;
                showToast("Escalating...", `Sending escalation request to IBM Db2 for ${trackingId}...`, "info", 2000);

                try {
                    const patchRes = await apiRequest(`/grievances/${encodeURIComponent(trackingId)}/status`, {
                        method: "PATCH",
                        body: JSON.stringify({
                            status: "Under Review",
                            priority: "Critical",
                            notes: "Grievance escalated by citizen to Joint Secretary / Senior Appellate Officer under Citizen Charter provisions.",
                            updated_by: "Citizen Escalation"
                        })
                    });

                    if (patchRes.ok) {
                        const patchData = await patchRes.json();
                        renderGrievance(patchData.data);
                        showToast("🚨 Grievance Escalated in IBM Db2!", "Escalated to Priority Review (Docket assigned)", "warning", 5000);
                    } else {
                        throw new Error(`HTTP ${patchRes.status}`);
                    }
                } catch (patchErr) {
                    console.error("Escalation error:", patchErr);
                    // Fallback local update
                    activeGrievance.escalated = true;
                    activeGrievance.priority = "Critical";
                    saveGrievance(activeGrievance);
                    renderGrievance(activeGrievance);
                    showToast("🚨 Grievance Escalated", "Marked as high priority review", "warning", 4000);
                }
            });
        }
    }

    // ==========================================================================
    // 9. Floating AI Assistant ("CPGRAMS Sahayak / मित्र")
    // ==========================================================================
    function initSahayakAssistant() {
        let widget = document.getElementById("sahayak-widget");
        if (!widget) {
            widget = document.createElement("div");
            widget.id = "sahayak-widget";
            widget.className = "sahayak-widget";
            widget.innerHTML = `
                <!-- Trigger Button -->
                <button type="button" class="sahayak-trigger" id="sahayak-trigger" aria-label="Open CPGRAMS AI Assistant">
                    <div class="sahayak-trigger-avatar">🤖</div>
                    <span>सहायक / AI Sahayak</span>
                    <span class="sahayak-trigger-badge"></span>
                </button>

                <!-- Chat Window -->
                <div class="sahayak-window hidden" id="sahayak-window" role="dialog" aria-label="CPGRAMS AI Assistant">
                    <div class="sahayak-header">
                        <div class="sahayak-header-title">
                            <div class="sahayak-avatar-header">🤖</div>
                            <div>
                                <h4 id="sahayak-title">CPGRAMS Sahayak</h4>
                                <span class="sahayak-header-sub"><span style="color:#22c55e;">●</span> Online • Gov AI Assistant</span>
                            </div>
                        </div>
                        <button type="button" class="sahayak-header-btn" id="sahayak-close" aria-label="Close Assistant">✕</button>
                    </div>

                    <div class="sahayak-body" id="sahayak-messages">
                        <div class="sahayak-msg sahayak-msg--bot" id="sahayak-greeting-msg">
                            Namaste! I am your CPGRAMS AI Assistant. How can I help you today? You can ask about filing a complaint, tracking status, or finding the right department.
                        </div>
                    </div>

                    <div class="sahayak-chips-container" id="sahayak-chips">
                        <button type="button" class="sahayak-chip" data-query="How to lodge a grievance?">📝 How to Lodge?</button>
                        <button type="button" class="sahayak-chip" data-query="Track demo grievance GRV-2026-4821">🔍 Track Grievance</button>
                        <button type="button" class="sahayak-chip" data-query="Ration card delay department">🌾 Ration Card Dept</button>
                        <button type="button" class="sahayak-chip" data-query="12-day escalation rules">🚨 Escalation Rules</button>
                        <button type="button" class="sahayak-chip" data-query="National Helpline numbers">📞 Helplines</button>
                    </div>

                    <div class="sahayak-footer">
                        <input type="text" class="sahayak-input" id="sahayak-input" placeholder="Type or speak your question..." aria-label="Type your message">
                        <button type="button" class="sahayak-btn-voice" id="sahayak-mic" title="Speak to Sahayak" aria-label="Voice input">
                            🎙️
                        </button>
                        <button type="button" class="sahayak-btn-send" id="sahayak-send" aria-label="Send message">
                            ➤
                        </button>
                    </div>
                </div>
            `;
            document.body.appendChild(widget);
        }

        const trigger = document.getElementById("sahayak-trigger");
        const windowEl = document.getElementById("sahayak-window");
        const closeBtn = document.getElementById("sahayak-close");
        const sendBtn = document.getElementById("sahayak-send");
        const micBtn = document.getElementById("sahayak-mic");
        const inputEl = document.getElementById("sahayak-input");
        const msgContainer = document.getElementById("sahayak-messages");
        const chipsContainer = document.getElementById("sahayak-chips");

        if (trigger && windowEl) {
            trigger.addEventListener("click", () => {
                windowEl.classList.toggle("hidden");
                if (!windowEl.classList.contains("hidden")) {
                    inputEl.focus();
                }
            });
        }

        if (closeBtn && windowEl) {
            closeBtn.addEventListener("click", () => {
                windowEl.classList.add("hidden");
            });
        }

        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && windowEl && !windowEl.classList.contains("hidden")) {
                windowEl.classList.add("hidden");
            }
        });

        function appendMessage(text, sender = "bot") {
            const msg = document.createElement("div");
            msg.className = `sahayak-msg sahayak-msg--${sender}`;
            msg.innerHTML = text;
            msgContainer.appendChild(msg);
            msgContainer.scrollTop = msgContainer.scrollHeight;
        }

        async function processBotResponse(query) {
            const q = query.toLowerCase();
            const lang = localStorage.getItem(STORAGE_KEY_LANG) || "en";
            const isHi = lang === "hi";

            // 1. Show dynamic tool-calling typing indicator
            const indicator = document.createElement("div");
            indicator.className = "sahayak-msg sahayak-msg--bot sahayak-indicator";
            indicator.innerHTML = `
                <span style="display:inline-flex;align-items:center;gap:0.4rem;color:#0043ce;font-size:0.8125rem;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1.2s linear infinite;"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
                    <em>Sahayak is consulting IBM Db2...</em>
                </span>
            `;
            msgContainer.appendChild(indicator);
            msgContainer.scrollTop = msgContainer.scrollHeight;

            // 2. Call backend Agentic Tool-Dispatcher endpoint
            try {
                const response = await fetch("/api/sahayak/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message: query, language: lang })
                });

                if (indicator) indicator.remove();

                if (response.ok) {
                    const data = await response.json();
                    appendMessage(data.reply, "bot");

                    // 1-Click Interactive Tracking Card if docket lookup tool was invoked
                    if (data.tool_used === "tool_track_docket" && data.data_payload && data.data_payload.found) {
                        const p = data.data_payload;
                        const card = document.createElement("div");
                        card.className = "sahayak-tracking-card";
                        card.style.cssText = "background: #f0f7ff; border: 1px solid #bae6fd; border-radius: 6px; padding: 0.75rem; margin-top: 0.5rem; font-size: 0.8125rem;";
                        card.innerHTML = `
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                                <strong style="color: #0043ce; font-family: monospace; font-size: 0.9375rem;">${p.tracking_id}</strong>
                                <span style="font-size: 0.7rem; font-weight: 700; background: ${p.status === 'Resolved' ? '#dcfce7' : '#fef3c7'}; color: ${p.status === 'Resolved' ? '#166534' : '#92400e'}; padding: 0.15rem 0.4rem; border-radius: 4px;">${p.status}</span>
                            </div>
                            <div style="color: #475569; margin-bottom: 0.5rem; font-size: 0.75rem;">${p.subject}</div>
                            <a href="track-status.html?id=${encodeURIComponent(p.tracking_id)}" class="btn btn--primary" style="display: block; text-align: center; font-size: 0.75rem; padding: 0.35rem 0.6rem; text-decoration: none; border-radius: 4px; color: #fff; background: #0043ce;">
                                View Live Timeline & Actions &rarr;
                            </a>
                        `;
                        msgContainer.appendChild(card);
                        msgContainer.scrollTop = msgContainer.scrollHeight;
                    }
                    return;
                }
            } catch (err) {
                console.warn("Sahayak API fetch offline, executing fallback client knowledge:", err);
                if (indicator) indicator.remove();
            }

            // 3. Fallback client-side rule matches if backend is unreachable

            const matchGrv = query.match(/GRV-\d{4}-\d{4}/i);
            if (matchGrv) {
                const id = matchGrv[0].toUpperCase();
                const record = findGrievance(id);
                if (record) {
                    appendMessage(isHi 
                        ? `📋 <strong>शिकायत संख्या ${record.id} का विवरण:</strong><br>• विभाग: ${record.department}<br>• स्थिति: <strong>${record.status}</strong><br>• दर्ज तिथि: ${record.filedDate}<br><a href="track-status.html?id=${record.id}" style="color:#0284c7;font-weight:bold;text-decoration:underline;">यहाँ क्लिक करके पूरी टाइमलाइन देखें &rarr;</a>`
                        : `📋 <strong>Grievance ${record.id} Status:</strong><br>• Dept: ${record.department}<br>• Status: <strong>${record.status}</strong><br>• Filed: ${record.filedDate}<br><a href="track-status.html?id=${record.id}" style="color:#0284c7;font-weight:bold;text-decoration:underline;">Click here to view full timeline &rarr;</a>`
                    );
                    return;
                } else {
                    appendMessage(isHi
                        ? `⚠️ शिकायत संख्या <strong>${id}</strong> नहीं मिली। कृपया पंजीकरण संख्या की जांच करें।`
                        : `⚠️ Grievance ID <strong>${id}</strong> not found. Please verify your registration number.`
                    );
                    return;
                }
            }

            if (q.includes("how to lodge") || q.includes("kaise darj") || q.includes("file complaint") || q.includes("অভিযোগ") || q.includes("புகார்") || q.includes("ఫిర్యాదు")) {
                appendMessage(isHi
                    ? `📝 <strong>शिकायत दर्ज करने के 5 आसान चरण:</strong><br>1. 'शिकायत दर्ज करें' पेज पर जाएं。<br>2. श्रेणी चुनें और विवरण लिखें (या माइक से बोलें) ।<br>3. विभाग का चुनाव करें。<br>4. दस्तावेज/फोटो संलग्न करें。<br>5. संपर्क विवरण भरकर जमा करें。<br><a href="lodge-grievance.html" style="color:#0284c7;font-weight:bold;">अभी शिकायत दर्ज करें &rarr;</a>`
                    : `📝 <strong>5 Simple Steps to Lodge a Grievance:</strong><br>1. Go to 'Lodge Grievance' page.<br>2. Select category and type or speak your issue.<br>3. Select the concerned Ministry/Department.<br>4. Upload photos/documents & tag GPS location.<br>5. Fill contact details and submit to get your <strong>GRV-2026-XXXX</strong> ID.<br><a href="lodge-grievance.html" style="color:#0284c7;font-weight:bold;">Lodge Grievance Now &rarr;</a>`
                );
            } else if (q.includes("track") || q.includes("status") || q.includes("stithi")) {
                const list = getAllGrievances();
                const latest = list[0] || defaultDemoGrievance;
                appendMessage(isHi
                    ? `🔍 आप अपनी पंजीकरण संख्या दर्ज करके स्थिति जान सकते हैं। उदाहरण के लिए, डेमो आईडी: <strong>${latest.id}</strong><br><a href="track-status.html?id=${latest.id}" style="color:#0284c7;font-weight:bold;">${latest.id} को ट्रैक करें &rarr;</a>`
                    : `🔍 Enter your tracking ID on the Track Status page. For example, try demo ID: <strong>${latest.id}</strong><br><a href="track-status.html?id=${latest.id}" style="color:#0284c7;font-weight:bold;">Track ${latest.id} Now &rarr;</a>`
                );
            } else if (q.includes("ration") || q.includes("rashan") || q.includes("food") || q.includes("khadya") || q.includes("রেশন") || q.includes("రేషన్")) {
                appendMessage(isHi
                    ? `🌾 राशन कार्ड, खाद्यान्न वितरण और कोटे से संबंधित शिकायतें <strong>खाद्य एवं सार्वजनिक वितरण विभाग (Department of Food & Public Distribution)</strong> के अंतर्गत आती हैं।`
                    : `🌾 Issues regarding Ration Cards, PDS grain quotas, and fair price shops are handled by the <strong>Department of Food & Public Distribution</strong>.`
                );
            } else if (q.includes("pension") || q.includes("epfo") || q.includes("pf") || q.includes("পেনশন")) {
                appendMessage(isHi
                    ? `👴 पेंशन एवं पीएफ से संबंधित शिकायतें <strong>पेंशन एवं पेंशनभोगी कल्याण विभाग (Department of Pension & Pensioners' Welfare)</strong> के अंतर्गत आती हैं।`
                    : `👴 Pension, EPF, gratuity, and retirement disputes are addressed by the <strong>Department of Pension & Pensioners' Welfare</strong>.`
                );
            } else if (q.includes("escalat") || q.includes("12 day") || q.includes("pending")) {
                appendMessage(isHi
                    ? `🚨 <strong>12-दिन एस्केलेशन नियम:</strong> यदि किसी शिकायत पर 12 दिनों तक कोई कार्रवाई नहीं होती है, तो नागरिक सीधे पोर्टल से उसे <strong>संयुक्त सचिव / अपीलीय अधिकारी</strong> को एस्केलेट कर सकते हैं।`
                    : `🚨 <strong>12-Day Escalation Protocol:</strong> If a grievance remains unresolved for over 12 days, citizens can click <em>'Escalate This Grievance'</em> to assign it priority status under the Joint Secretary / Appellate Authority.`
                );
            } else if (q.includes("help") || q.includes("number") || q.includes("contact") || q.includes("phone")) {
                appendMessage(isHi
                    ? `📞 <strong>राष्ट्रीय सहायता केंद्र:</strong><br>• टोल-फ्री हेल्पलाइन: <strong>1800-11-4000</strong><br>• ईमेल: <strong>cpgrams-helpdesk@nic.in</strong><br>• समय: सुबह 9:00 से शाम 6:00 (सोमवार से शनिवार)`
                    : `📞 <strong>CPGRAMS Citizen Helplines:</strong><br>• Toll-Free Helpline: <strong>1800-11-4000</strong><br>• Email: <strong>cpgrams-helpdesk@nic.in</strong><br>• Hours: 9:00 AM – 6:00 PM (Mon–Sat)`
                );
            } else {
                appendMessage(isHi
                    ? `धन्यवाद! आपकी सहायता के लिए मैं हमेशा उपलब्ध हूँ। आप पोर्टल पर <strong>शिकायत दर्ज कर सकते हैं</strong>, <strong>स्थिति ट्रैक कर सकते हैं</strong>, या ऊपर दिए गए क्विक बटन दबा सकते हैं।`
                    : `Thank you for reaching out! You can easily <strong>Lodge a Grievance</strong>, <strong>Track your Status</strong>, or click any of the quick suggestions above for immediate assistance.`
                );
            }
        }

        function handleSend() {
            const query = inputEl.value.trim();
            if (!query) return;
            appendMessage(query, "user");
            inputEl.value = "";
            setTimeout(() => processBotResponse(query), 500);
        }

        if (sendBtn && inputEl) {
            sendBtn.addEventListener("click", handleSend);
            inputEl.addEventListener("keypress", (e) => {
                if (e.key === "Enter") handleSend();
            });
        }

        if (chipsContainer) {
            chipsContainer.querySelectorAll(".sahayak-chip").forEach(chip => {
                chip.addEventListener("click", () => {
                    const q = chip.getAttribute("data-query") || chip.textContent;
                    appendMessage(q, "user");
                    setTimeout(() => processBotResponse(q), 400);
                });
            });
        }

        // Voice button inside Assistant
        if (micBtn) {
            const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
            let sahayakRec = null;

            micBtn.addEventListener("click", () => {
                if (micBtn.classList.contains("listening")) {
                    if (sahayakRec) {
                        sahayakRec.stop();
                        sahayakRec = null;
                    }
                    micBtn.classList.remove("listening");
                    return;
                }

                if (SpeechRec) {
                    try {
                        const rec = new SpeechRec();
                        rec.continuous = false;
                        rec.interimResults = true;
                        const lang = localStorage.getItem(STORAGE_KEY_LANG) || "en";
                        rec.lang = voiceLocaleMap[lang] || "en-IN";

                        let basePrefix = "";

                        rec.onstart = () => {
                            if (inputEl) {
                                basePrefix = inputEl.value.trim();
                            }
                            micBtn.classList.add("listening");
                            showToast("🎙️ Sahayak Listening", `Speak your question in ${languageNames[lang] || 'your language'}...`, "info", 2000);
                        };

                        rec.onresult = (e) => {
                            let finalTranscript = "";
                            let interimTranscript = "";
                            for (let i = 0; i < e.results.length; ++i) {
                                const transcript = e.results[i][0].transcript;
                                if (e.results[i].isFinal) {
                                    finalTranscript += (finalTranscript ? " " : "") + transcript.trim();
                                } else {
                                    interimTranscript += (interimTranscript ? " " : "") + transcript.trim();
                                }
                            }

                            const parts = [];
                            if (basePrefix) parts.push(basePrefix);
                            if (finalTranscript) parts.push(finalTranscript);
                            if (interimTranscript) parts.push(interimTranscript);

                            if (inputEl) {
                                inputEl.value = parts.join(" ");
                            }
                        };

                        rec.onerror = (e) => {
                            console.warn("Sahayak speech error:", e.error);
                            micBtn.classList.remove("listening");
                            sahayakRec = null;
                            if (e.error !== "no-speech") {
                                showToast("Voice Assistant", "Could not capture voice; please type your question.", "warning", 2000);
                            }
                        };

                        rec.onend = () => {
                            micBtn.classList.remove("listening");
                            sahayakRec = null;
                            if (inputEl && inputEl.value.trim()) {
                                handleSend();
                            }
                        };

                        sahayakRec = rec;
                        rec.start();
                    } catch (e) {
                        micBtn.classList.remove("listening");
                        sahayakRec = null;
                    }
                } else {
                    showToast("Voice Unavailable", "Browser does not support direct voice input.", "info");
                }
            });
        }
    }

    // ==========================================================================
    // 10. Grievance History / Session Drawer Module
    // ==========================================================================
    function initGrievanceHistoryDrawer() {
        let backdrop = document.getElementById("drawer-backdrop");
        let drawer = document.getElementById("history-drawer");

        if (!drawer) {
            backdrop = document.createElement("div");
            backdrop.id = "drawer-backdrop";
            backdrop.className = "drawer-backdrop";
            document.body.appendChild(backdrop);

            drawer = document.createElement("div");
            drawer.id = "history-drawer";
            drawer.className = "history-drawer";
            drawer.innerHTML = `
                <div class="history-drawer-header">
                    <h3>📋 My Recent Grievances</h3>
                    <button type="button" class="sahayak-header-btn" id="drawer-close" aria-label="Close Grievance Drawer">✕</button>
                </div>
                <div class="history-drawer-body" id="drawer-body">
                    <!-- Ticket list rendered dynamically -->
                </div>
            `;
            document.body.appendChild(drawer);
        }

        const closeBtn = document.getElementById("drawer-close");

        function openDrawer() {
            updateGrievanceDrawerUI();
            drawer.classList.add("open");
            backdrop.classList.add("open");
        }

        function closeDrawer() {
            drawer.classList.remove("open");
            backdrop.classList.remove("open");
        }

        document.querySelectorAll("#btn-history-toggle, .btn-history-toggle").forEach(btn => {
            btn.addEventListener("click", openDrawer);
        });

        if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
        if (backdrop) backdrop.addEventListener("click", closeDrawer);
    }

    function updateGrievanceDrawerUI() {
        const body = document.getElementById("drawer-body");
        if (!body) return;

        const list = getAllGrievances();
        if (list.length === 0) {
            body.innerHTML = `
                <div style="text-align: center; padding: 2rem 1rem; color: var(--color-text-muted);">
                    <span style="font-size: 2.5rem; display: block; margin-bottom: 0.75rem;">📭</span>
                    <h4 style="margin: 0 0 0.5rem 0; color: var(--color-navy);">No Grievances Found</h4>
                    <p style="font-size: 0.875rem;">You haven't filed any grievances in this browser session yet.</p>
                    <a href="lodge-grievance.html" class="btn btn--primary btn--sm mt-3" style="display: inline-block; margin-top: 1rem;">Lodge New Grievance &rarr;</a>
                </div>
            `;
            return;
        }

        body.innerHTML = "";
        list.forEach(item => {
            const card = document.createElement("div");
            card.className = "history-ticket-card";
            card.innerHTML = `
                <div class="history-ticket-header">
                    <span class="history-ticket-id">${item.id}</span>
                    <span class="status-badge ${item.escalated ? 'status-badge--escalated' : 'status-badge--review'}" style="font-size: 0.6875rem; padding: 2px 8px;">
                        ${item.escalated ? '🚨 Escalated' : '⏳ ' + item.status}
                    </span>
                </div>
                <div class="history-ticket-title">${item.subject || 'Grievance Application'}</div>
                <div class="history-ticket-meta">Dept: ${item.department} • Filed: ${item.filedDate || 'Recent'}</div>
                <div class="history-ticket-actions">
                    <a href="track-status.html?id=${item.id}" class="btn btn--primary btn--sm" style="padding: 4px 10px; font-size: 0.75rem;">Track Status &rarr;</a>
                    <button type="button" class="btn btn--ghost btn--sm copy-id-btn" data-id="${item.id}" style="padding: 4px 10px; font-size: 0.75rem;">Copy ID</button>
                </div>
            `;

            card.querySelector(".copy-id-btn").addEventListener("click", () => {
                navigator.clipboard.writeText(item.id).then(() => {
                    showToast("ID Copied!", `Copied ${item.id} to clipboard`, "success", 2000);
                });
            });

            body.appendChild(card);
        });
    }

    // ==========================================================================
    // 11. Mobile Menu & General UI Utilities
    // ==========================================================================
    function initMobileMenu() {
        const toggleBtns = document.querySelectorAll(".menu-toggle, .mobile-menu-toggle, .main-header__toggle, .hamburger");
        const nav = document.querySelector(".main-nav, .main-header__nav");

        toggleBtns.forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                if (nav) {
                    nav.classList.toggle("open");
                    const isOpen = nav.classList.contains("open");
                    toggleBtns.forEach(b => b.setAttribute("aria-expanded", isOpen ? "true" : "false"));
                }
            });
        });

        if (nav) {
            // Close mobile menu when clicking a nav link
            nav.querySelectorAll("a").forEach(link => {
                link.addEventListener("click", () => {
                    nav.classList.remove("open");
                    toggleBtns.forEach(btn => btn.setAttribute("aria-expanded", "false"));
                });
            });

            // Close mobile menu when clicking outside
            document.addEventListener("click", (e) => {
                if (nav.classList.contains("open") && !nav.contains(e.target) && !Array.from(toggleBtns).some(b => b.contains(e.target))) {
                    nav.classList.remove("open");
                    toggleBtns.forEach(btn => btn.setAttribute("aria-expanded", "false"));
                }
            });

            // Close on Escape key
            document.addEventListener("keydown", (e) => {
                if (e.key === "Escape" && nav.classList.contains("open")) {
                    nav.classList.remove("open");
                    toggleBtns.forEach(btn => btn.setAttribute("aria-expanded", "false"));
                }
            });
        }

        // Copy button in confirmation
        document.querySelectorAll(".copy-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const regText = document.querySelector(".reg-value")?.textContent || "";
                if (regText) {
                    navigator.clipboard.writeText(regText).then(() => {
                        showToast("Copied to Clipboard", `Registration ID ${regText} copied.`, "success", 2000);
                    });
                }
            });
        });
    }

    // ==========================================================================
    // 12. Document Ready Initialization
    // ==========================================================================
    document.addEventListener("DOMContentLoaded", () => {
        initAccessibility();
        initLanguageToggle();
        initMobileMenu();
        initLodgeGrievancePage();
        initTrackStatusPage();
        initSahayakAssistant();
        initGrievanceHistoryDrawer();
    });

})();
