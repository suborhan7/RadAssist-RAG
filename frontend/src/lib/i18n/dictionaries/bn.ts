/**
 * Bengali (বাংলা) dictionary — a full FIRST-PASS translation by the build,
 * PROVISIONAL and awaiting review by a Bengali-speaking clinician. This matches
 * the project's existing convention for its Bengali report headers (see
 * `label_mapping.yaml` / the Bengali report-header work), which also ship
 * marked-provisional pending clinical review.
 *
 * Every key in `en.ts` must appear here (parity is checked by check-i18n.mjs).
 * Product names (RadAssist, BiomedCLIP, ChromaDB, FastAPI, Ollama, GPU), codes,
 * IDs, dates and numbers are intentionally left in Latin script — they are not
 * translated anywhere in the UI.
 */
import type { Dict } from "../shared";

export const bn: Dict = {
  // ── common ────────────────────────────────────────────────────────────────
  "common.signIn": "সাইন ইন",
  "common.register": "নিবন্ধন",
  "common.dashboard": "ড্যাশবোর্ড",
  "common.email": "ইমেইল",
  "common.password": "পাসওয়ার্ড",
  "common.researchPrototype": "গবেষণা প্রোটোটাইপ",
  "common.cancel": "বাতিল",
  "common.save": "সংরক্ষণ",
  "common.retry": "আবার চেষ্টা করুন",
  "common.loading": "লোড হচ্ছে…",
  "common.copy": "কপি করুন",
  "common.copied": "কপি হয়েছে",
  "common.copyFailed": "কপি ব্যর্থ",

  // ── nav (left rail) ───────────────────────────────────────────────────────
  "nav.queue": "সারি",
  "nav.find": "রোগী খুঁজুন",
  "nav.patients": "রোগীরা",
  "nav.newExam": "নতুন পরীক্ষা",
  "nav.workspace": "ওয়ার্কস্পেস",
  "nav.explain": "ব্যাখ্যা",
  "nav.compare": "তুলনা",
  "nav.settings": "সেটিংস",
  "nav.signOut": "সাইন আউট",
  "nav.signingOut": "সাইন আউট হচ্ছে…",
  "nav.back": "পিছনে",
  "nav.requiresPatient": "আগে একজন রোগী বেছে নিন",
  "nav.requiresReport": "আগে একটি রিপোর্ট বেছে নিন",

  // ── language toggle ───────────────────────────────────────────────────────
  "lang.label": "ভাষা",

  // ── theme toggle ──────────────────────────────────────────────────────────
  "theme.label": "চেহারা",
  "theme.dark": "গাঢ়",
  "theme.light": "উজ্জ্বল",

  // ── landing ───────────────────────────────────────────────────────────────
  "landing.headerCtaSignIn": "সাইন ইন",
  "landing.headerCtaDashboard": "ড্যাশবোর্ড",
  "landing.ctaSignIn": "আপনার ওয়ার্কস্পেসে সাইন ইন করুন",
  "landing.ctaDashboard": "আপনার ড্যাশবোর্ডে যান",
  "landing.heroTitle": "প্রমাণভিত্তিক বুকের এক্স-রে রিপোর্টিং।",
  "landing.heroSubtitle":
    "প্রতিটি এআই খসড়া বাস্তব, পুনরুদ্ধার করা পূর্ববর্তী কেসের উপর ভিত্তি করে তৈরি। কখনও শূন্য থেকে তৈরি নয়, এবং কখনও রেডিওলজিস্ট ছাড়া স্বাক্ষরিত নয়।",
  "landing.aiDraft": "এআই খসড়া",
  "landing.proofPhrase1": "উভয় ফুসফুস জুড়ে ছড়ানো ইন্টারস্টিশিয়াল দাগ স্পষ্ট",
  "landing.proofConnective": ", যা সঙ্গতিপূর্ণ ",
  "landing.proofPhrase2": "তীব্র সংক্রমণের বদলে ফাইব্রোটিক পরিবর্তনের সাথে",
  "landing.proofTrace": "প্রতিটি নিম্নরেখাঙ্কিত বক্তব্য তার সমর্থনকারী পুনরুদ্ধার করা কেসগুলিতে ফিরে যায়।",
  "landing.neverFinalized": "কোনো রিপোর্ট কখনও রেডিওলজিস্ট ছাড়া চূড়ান্ত করা হয়নি।",
  "landing.pipelineTitle": "একটি রিপোর্ট কীভাবে ভিত্তি পায়",
  "landing.stageChestXray": "বুকের এক্স-রে",
  "landing.stagePhi": "PHI সুরক্ষা",
  "landing.stageSimilar": "অনুরূপ কেস",
  "landing.stageAiDraft": "এআই খসড়া",
  "landing.stageReview": "রেডিওলজিস্ট পর্যালোচনা",
  "landing.footer": "গবেষণা প্রোটোটাইপ। ক্লিনিক্যাল ব্যবহারের জন্য নয়। প্রতিটি রিপোর্টের জন্য একজন যোগ্য রেডিওলজিস্টের পর্যালোচনা প্রয়োজন।",

  // ── login ─────────────────────────────────────────────────────────────────
  "login.filmTitle": "পুনরুদ্ধার-ভিত্তিক বুকের এক্স-রে রিপোর্টিং।",
  "login.filmBody":
    "প্রতিটি এআই খসড়া যে পুনরুদ্ধার করা কেসের উপর ভিত্তি করে তৈরি তা উদ্ধৃত করে। কোনো রিপোর্ট কখনও রেডিওলজিস্ট ছাড়া চূড়ান্ত করা হয়নি।",
  "login.notForClinical": "ক্লিনিক্যাল ব্যবহারের জন্য নয়। প্রতিটি রিপোর্টের জন্য একজন যোগ্য রেডিওলজিস্টের পর্যালোচনা প্রয়োজন।",
  "login.heading": "সাইন ইন",
  "login.subtitle": "RadAssist-RAG · রেডিওলজিস্ট কর্মপ্রবাহ",
  "login.systemStatus": "সিস্টেম স্ট্যাটাস",
  "login.backendUnreachable": "ব্যাকএন্ডে পৌঁছানো যাচ্ছে না।",
  "login.signingIn": "সাইন ইন হচ্ছে…",
  "login.noAccount": "অ্যাকাউন্ট নেই?",
  "login.errCredentials": "ইমেইল বা পাসওয়ার্ড ভুল।",
  "login.errFailed": "সাইন ইন ব্যর্থ হয়েছে।",

  // ── register ──────────────────────────────────────────────────────────────
  "register.title": "একটি ডাক্তার অ্যাকাউন্ট নিবন্ধন করুন",
  "register.subtitle": "রোগী নিবন্ধন আপনার বিভাগের সাথে ভাগ করা হয়। আপনার অস্বাক্ষরিত খসড়াগুলি নয়।",
  "register.fullName": "পূর্ণ নাম, যেমন রিপোর্টে ছাপা হবে",
  "register.qualifications": "যোগ্যতা",
  "register.bmdcOptional": "BMDC নম্বর (ঐচ্ছিক)",
  "register.creating": "অ্যাকাউন্ট তৈরি হচ্ছে…",
  "register.create": "অ্যাকাউন্ট তৈরি করুন",
  "register.already": "ইতিমধ্যে নিবন্ধিত?",
  "register.sigBlock": "স্বাক্ষর ব্লক · লাইভ",
  "register.yourName": "আপনার নাম",
  "register.bmdcNotEntered": "BMDC প্রবেশ করানো হয়নি",
  "register.sigNote":
    "যেমন প্রবেশ করানো হয়েছে তেমনই নথিভুক্ত এবং আপনার স্বাক্ষরিত প্রতিটি রিপোর্টে ছাপা হয়। এই সিস্টেমের BMDC নিবন্ধনে কোনো প্রবেশাধিকার নেই এবং এটি যাচাই করতে পারে না।",
  "register.errExists": "এই ইমেইল দিয়ে একটি অ্যাকাউন্ট ইতিমধ্যে বিদ্যমান।",
  "register.errFailed": "নিবন্ধন ব্যর্থ হয়েছে।",

  // ── dashboard (reading queue) ─────────────────────────────────────────────
  "dashboard.title": "পঠন সারি",
  "dashboard.queueFallback": "আপনার পঠন সারি",
  "dashboard.queueLoading": "আপনার সারি লোড হচ্ছে…",
  "dashboard.awaiting": (p) => `${Number(p.count)}টি রিপোর্ট আপনার জন্য অপেক্ষা করছে।`,
  "dashboard.clear": "আপনার সারি পরিষ্কার।",
  "dashboard.clearNamed": (p) => `আপনার সারি পরিষ্কার, ${String(p.name)}।`,
  "dashboard.openOldest": "সবচেয়ে পুরনোটি খুলুন",
  "dashboard.waitingDays": (p) => `${Number(p.count)} দিন ধরে অপেক্ষমাণ`,
  "dashboard.examToday": "আজকের পরীক্ষা",
  "dashboard.reportsByYou": "আপনার রিপোর্ট",
  "dashboard.patientsReported": "রিপোর্টকৃত রোগী",
  "dashboard.errStats": "ড্যাশবোর্ড পরিসংখ্যান লোড করা যায়নি।",
  "dashboard.errRecent": "সাম্প্রতিক কার্যকলাপ লোড করা যায়নি।",
  "dashboard.colPatient": "রোগী",
  "dashboard.colWaiting": "অপেক্ষমাণ",
  "dashboard.colStatus": "স্ট্যাটাস",
  "dashboard.colEdited": "সম্পাদিত",
  "dashboard.loadingQueue": "সারি লোড হচ্ছে…",
  "dashboard.emptyQueue": "এখনও কোনো রিপোর্ট নেই। সারি তৈরি করতে একটি নতুন পরীক্ষা শুরু করুন।",
  "dashboard.delete": "বাতিল করুন",
  "dashboard.deleteConfirm": "নিশ্চিত করুন",
  "dashboard.deleteAria": (p) => `${p.patient}-এর খসড়া বাতিল করুন`,
  "dashboard.errDelete": "এই খসড়াটি বাতিল করা যায়নি।",
  "dashboard.noPatientLinked": "কোনো রোগী সংযুক্ত নেই",
  "dashboard.actionReview": "পর্যালোচনা",
  "dashboard.actionOpen": "খুলুন",
  "dashboard.actionResume": "চালিয়ে যান",
  "dashboard.unitMin": (p) => `${Number(p.count)} মিনিট`,
  "dashboard.unitHours": (p) => `${Number(p.count)} ঘন্টা`,
  "dashboard.unitDays": (p) => `${Number(p.count)} দিন`,
  "dashboard.ownership": (p) =>
    `আপনি হাসপাতালের ${Number(p.total)} জন নিবন্ধিত রোগীর মধ্যে ${Number(p.reported)} জনের রিপোর্ট করেছেন। আপনি যেকোনো সহকর্মীর রোগী খুলতে পারেন; তবে তাদের অস্বাক্ষরিত খসড়া খুলতে পারবেন না।`,

  // ── shared verbs / patient actions ────────────────────────────────────────
  "common.open": "খুলুন",
  "common.registerNewPatient": "নতুন রোগী নিবন্ধন করুন",

  // ── find patient (search) ─────────────────────────────────────────────────
  "search.byCode": "রোগী কোড দিয়ে",
  "search.byNameDob": "নাম ও জন্ম তারিখ দিয়ে",
  "search.patientCode": "রোগী কোড",
  "search.name": "নাম",
  "search.dob": "জন্ম তারিখ",
  "search.searching": "খোঁজা হচ্ছে…",
  "search.search": "খুঁজুন",
  "search.helper": "একটি কোড, অথবা একটি নাম ও জন্ম তারিখ। বানান কখনও রোগী খুঁজে না পাওয়ার কারণ নয়।",
  "search.errFailed": "অনুসন্ধান ব্যর্থ হয়েছে।",
  "search.zeroMatches":
    "একটি সঠিকভাবে গঠিত অনুসন্ধান যা কিছুই খুঁজে পায় না তা কোনো ত্রুটি নয়। রোগীকে নিবন্ধন করুন, অথবা একটি সাধারণ নাম সংকুচিত করতে জন্ম তারিখ যোগ করুন।",
  "search.matches": (p) => `${Number(p.count)}টি ম্যাচ`,

  // ── patients directory (list all + name/ID search) ────────────────────────
  "directory.searchPlaceholder": "নাম বা রোগী আইডি দিয়ে খুঁজুন",
  "directory.colId": "রোগী আইডি",
  "directory.count": (p) => `${Number(p.count)}টি রোগী`,
  "directory.empty": "এখনও কোনো রোগী নিবন্ধিত নেই।",
  "directory.noMatches": "আপনার অনুসন্ধানের সাথে কোনো রোগী মেলেনি।",
  "directory.loading": "রোগীদের তালিকা লোড হচ্ছে…",
  "directory.errLoad": "রোগীদের তালিকা লোড করা যায়নি।",
  "directory.clear": "সাফ করুন",

  // ── patient profile ───────────────────────────────────────────────────────
  "patient.errLoad": "রোগীর প্রোফাইল লোড করা যায়নি।",
  "patient.loading": "রোগীর প্রোফাইল লোড হচ্ছে…",
  "patient.compareLatestTwo": "সর্বশেষ দুটি তুলনা করুন",
  "patient.years": (p) => `${Number(p.count)} বছর`,
  "patient.born": "জন্ম",
  "patient.onRecord": "নথিভুক্ত",
  "patient.studies": (p) => `${Number(p.count)}টি স্টাডি`,
  "patient.since": (p) => `${String(p.since)} থেকে`,
  "patient.priorStudies": "পূর্ববর্তী স্টাডি · একই রোগী",
  "patient.noPriors": "এই রোগীর জন্য এখনও কোনো পূর্ববর্তী ভিজিট নথিভুক্ত নেই।",
  "patient.noImpression": "(কোনো ইম্প্রেশন নথিভুক্ত নেই)",
  "patient.openReport": "রিপোর্ট খুলুন",
  "patient.compareWithThis": "এটির সাথে তুলনা করুন",
  "patient.priorNote":
    "পূর্ববর্তী স্টাডিগুলি সময়ের সাথে এই রোগীর। আর্কাইভ কেস, সাদৃশ্য অনুসারে পুনরুদ্ধার করা অন্য রোগীদের ফিল্ম, এখানে কখনও দেখা যায় না; সেগুলি কেবল ওয়ার্কস্পেসের ভিতরে বিদ্যমান।",

  // ── register patient (patients/new) ───────────────────────────────────────
  "newPatient.title": "রোগী নিবন্ধন করুন",
  "newPatient.fullName": "পূর্ণ নাম",
  "newPatient.sex": "লিঙ্গ",
  "newPatient.sexFemale": "মহিলা",
  "newPatient.sexMale": "পুরুষ",
  "newPatient.sexOther": "অন্যান্য",
  "newPatient.registering": "নিবন্ধন হচ্ছে…",
  "newPatient.errFailed": "রোগী নিবন্ধন করা যায়নি।",
  "newPatient.registeredPre": "রোগী নিবন্ধিত হয়েছে:",
  "newPatient.registeredPost": "। প্রোফাইল খোলা হচ্ছে…",
  "newPatient.willAssign": "বরাদ্দ করা হবে",
  "newPatient.assignNote":
    "ক্রমিক ও স্থায়ী, নিবন্ধনের সময় বরাদ্দ করা হয়। অভ্যর্থনায় ফিল্মের খামে লেখা হয়।",

  // ── new examination (upload → retrieve → questionnaire → generate) ─────────
  "upload.crumbPatient": "রোগী",
  "upload.stepUploading": "বুকের এক্স-রে আপলোড হচ্ছে",
  "upload.stepRetrieving": "অনুরূপ কেস পুনরুদ্ধার হচ্ছে",
  "upload.stepQuestionnaire": "ক্লিনিক্যাল প্রশ্নমালা",
  "upload.stepGenerating": "এআই রিপোর্ট তৈরি হচ্ছে",
  "upload.dropFilm": "বুকের ফিল্মটি এখানে ছাড়ুন",
  "upload.chooseFile": "একটি ফাইল নির্বাচন করুন",
  "upload.altSelected": "নির্বাচিত বুকের এক্স-রে",
  "upload.altMasking": "বুকের এক্স-রে, মাস্কিং চলছে",
  "upload.dragReveal": "মূলটি দেখাতে টেনে আনুন",
  "upload.neverStored": "মূল কখনও সংরক্ষিত হয় না",
  "upload.startTitle": "একটি নতুন পরীক্ষা শুরু করুন",
  "upload.startDesc":
    "বাঁ দিকে বুকের ফিল্মটি ছাড়ুন। এটি আপলোডের সময় মাস্ক করা হয়, তারপর আর্কাইভের সাথে মেলানো হয় এবং খসড়া তৈরি হয়। সবকিছু স্থানীয়ভাবে চলে; কিছুই ভবনের বাইরে যায় না।",
  "upload.startBtn": "পরীক্ষা শুরু করুন",
  "upload.running": "পাইপলাইন চলছে",
  "upload.optionalQuestions": "ঐচ্ছিক ক্লিনিক্যাল প্রশ্ন",
  "upload.basedOnPre": "শীর্ষ প্রার্থী লেবেলের উপর ভিত্তি করে",
  "upload.basedOnPost": "। আপনার উত্তরগুলি প্রম্পটে অন্তর্ভুক্ত হয় এবং রিপোর্টের সাথে সংরক্ষিত থাকে।",
  "upload.reRetrieve": "উত্তরসহ পুনরায় পুনরুদ্ধার করুন",
  "upload.skipDraft": "এড়িয়ে গিয়ে খসড়া তৈরি করুন",
  "upload.skipNote": "এড়িয়ে যাওয়া রিপোর্টে নথিভুক্ত হয়।",
  "upload.runningNote": "পুনরুদ্ধার ও খসড়া তৈরি চলছে। স্থানীয় হার্ডওয়্যারে এটি কয়েক সেকেন্ড সময় নিতে পারে।",
  "upload.errRetrieval": "পুনরুদ্ধার ব্যর্থ হয়েছে।",
  "upload.errQuestionnaire": "প্রশ্নমালা লোড করা যায়নি।",
  "upload.errGeneration": "রিপোর্ট তৈরি ব্যর্থ হয়েছে।",

  // ── radiologist workspace ─────────────────────────────────────────────────
  "workspace.errLoad": "রিপোর্ট লোড করা যায়নি।",
  "workspace.errSave": "সম্পাদনা সংরক্ষণ করা যায়নি।",
  "workspace.errRestore": "এআই খসড়া পুনরুদ্ধার করা যায়নি।",
  "workspace.errRegen": "সেকশন পুনরায় তৈরি করা যায়নি।",
  "workspace.loading": "রিপোর্ট লোড হচ্ছে…",
  "workspace.reportFallback": "রিপোর্ট",
  "workspace.confirmLeave": "আপনার একটি অসংরক্ষিত সম্পাদনা চলছে। সংরক্ষণ ছাড়াই চলে যাবেন?",
  "workspace.confirmRestore": "আপনার সম্পাদনাগুলি মূল এআই খসড়া দিয়ে প্রতিস্থাপন করবেন? এটি বাতিল করা যাবে না।",
  "workspace.askAbout": "এই রিপোর্ট সম্পর্কে জিজ্ঞাসা করুন",
  "workspace.showChanges": "খসড়ার তুলনায় পরিবর্তন",
  "workspace.hideChanges": "খসড়ার তুলনায় পরিবর্তন লুকান",
  "workspace.finalize": "চূড়ান্ত করুন",
  "workspace.belongsToPre": "এই রিপোর্টটি",
  "workspace.belongsToPost": " এর। আপনি এটি পড়তে এবং এর সাথে তুলনা করতে পারেন।",
  "workspace.anotherDoctor": "অন্য একজন ডাক্তার",
  "workspace.phiMasked": "PHI মাস্ক করা",
  "workspace.altXrayPrefix": "বুকের এক্স-রে",
  "workspace.finalizedReport": "চূড়ান্ত রিপোর্ট",
  "workspace.aiReport": "এআই রিপোর্ট",
  "workspace.restoring": "পুনরুদ্ধার হচ্ছে…",
  "workspace.restoreDraft": "খসড়া পুনরুদ্ধার করুন",
  "workspace.finalizedBy": (p) => `${String(p.name)} কর্তৃক ${String(p.date)} তারিখে চূড়ান্ত করা হয়েছে`,
  "workspace.thisDoctor": "এই ডাক্তার",
  "workspace.validation": "যাচাইকরণ",
  "workspace.noWarnings": "কোনো যাচাইকরণ সতর্কতা নেই।",
  "workspace.explainReport": "রিপোর্ট ব্যাখ্যা করুন",
  "workspace.comparePrevious": "পূর্ববর্তীটির সাথে তুলনা করুন",
  "workspace.downloadPdf": "PDF ডাউনলোড করুন",
  "workspace.downloadPdfTitle": "এই থিসিসের আওতার বাইরে (হিমায়িত ফেজ 12 স্পেক)",
  "workspace.draftedFrom": (p) =>
    `${Number(p.count)}টি আর্কাইভ কেস থেকে খসড়া তৈরি, তারপর রিপোর্টকারী রেডিওলজিস্ট কর্তৃক পর্যালোচিত ও সম্পাদিত। এটি একটি স্বয়ংক্রিয় রোগনির্ণয় নয়।`,
  "workspace.tabEvidence": "প্রমাণ",
  "workspace.tabAgreement": "ঐকমত্য",
  "workspace.tabAlternatives": "বিকল্প",
  "workspace.archiveCases": (p) => `আর্কাইভ কেস · অন্যান্য রোগী (${Number(p.count)})`,
  "workspace.presentInSet": "পুনরুদ্ধার করা সেটে উপস্থিত",
  "workspace.countOfK": (p) => `${Number(p.k)} এর মধ্যে ${Number(p.count)}`,
  "workspace.altNotePre": "এই তালিকা থেকে অনুপস্থিতির অর্থ কোনো পুনরুদ্ধার করা কেস লেবেলটি বহন করেনি।",
  "workspace.altNoteEmph": "এটি কোনো বর্জন নয়।",
  "workspace.altNotePost": "কেবল উপস্থিত লেবেলগুলি রিপোর্ট করা হয়, একটি সম্পূর্ণ ইতিবাচক বা নেতিবাচক শ্রেণিবিন্যাস নয়।",

  // ── comparison workspace ──────────────────────────────────────────────────
  "compare.errCurrent": "বর্তমান রিপোর্ট লোড করা যায়নি।",
  "compare.errNoPatient": "এই রিপোর্টের সাথে কোনো রোগী সংযুক্ত নেই, তাই এটি রোগীর ইতিহাসের সাথে তুলনা করা যাবে না।",
  "compare.errGenerate": "তুলনা তৈরি করা যায়নি।",
  "compare.errPrevious": "পূর্ববর্তী রিপোর্ট লোড করা যায়নি।",
  "compare.stepGenerating": "তুলনা তৈরি হচ্ছে",
  "compare.daysApart": (p) => `${Number(p.count)} দিনের ব্যবধান`,
  "compare.backToWorkspace": "ওয়ার্কস্পেসে ফিরে যান",
  "compare.reviewBanner": "ডাক্তারের পর্যালোচনা প্রয়োজন। এই এআই-উৎপন্ন তুলনাটি একটি খসড়া, চূড়ান্ত রায় নয়।",
  "compare.priorEyebrow": (p) => `পূর্ববর্তী · ${String(p.date)}`,
  "compare.thisStudyEyebrow": (p) => `এই স্টাডি · ${String(p.date)}`,
  "compare.altPrior": "পূর্ববর্তী বুকের এক্স-রে",
  "compare.altCurrent": "বর্তমান বুকের এক্স-রে",
  "compare.impression": "ইম্প্রেশন",
  "compare.none": "(কিছু নেই)",
  "compare.resolved": "নিরাময়প্রাপ্ত",
  "compare.persistent": "স্থায়ী",
  "compare.new": "নতুন",
  "compare.noneLower": "কিছু নেই",
  "compare.narrativeHeading": "বিবরণ · বাঁ দিকের বিভাজন থেকে মডেল কর্তৃক লিখিত",
  "compare.provenanceNote": (p) =>
    `নিরাময়প্রাপ্ত, স্থায়ী ও নতুন ফলাফলগুলি ComparisonService দ্বারা গণনা করা হয় (নির্ধারিত), স্টাডিগুলির মধ্যে ${Number(p.days)} দিনের ব্যবধান। বিবরণটি কেবল সেই পার্থক্য থেকে একটি LLM দ্বারা তৈরি; পার্থক্যটি নিজে মডেল দ্বারা নির্ধারিত হয় না।`,

  // ── explainability ────────────────────────────────────────────────────────
  "explain.q1": "এই ইম্প্রেশন কেন?",
  "explain.q2": "কোন পুনরুদ্ধার করা কেসটি সবচেয়ে কাছের?",
  "explain.q3": "কী এই ইম্প্রেশন পরিবর্তন করবে?",
  "explain.err502": (p) => `এআই সহকারী সাময়িকভাবে অনুপলব্ধ (LLM ট্রান্সপোর্ট ব্যর্থতা): ${String(p.msg)}`,
  "explain.err404": (p) => `রিপোর্ট পাওয়া যায়নি: ${String(p.msg)}`,
  "explain.errGeneric": "একটি উত্তর পাওয়া যায়নি।",
  "explain.stepAsking": "এআই সহকারীকে জিজ্ঞাসা করা হচ্ছে",
  "explain.labelQuestion": "আপনার প্রশ্ন",
  "explain.labelAnswer": "উত্তর",
  "explain.aiExplanation": "এআই ব্যাখ্যা",
  "explain.labelImpression": "ইম্প্রেশন",
  "explain.labelEvidence": "প্রমাণ",
  "explain.labelFindings": "এই রিপোর্টের ফাইন্ডিংস",
  "explain.labelReasoning": "মডেলের যুক্তি",
  "explain.hideReasoning": "লুকান",
  "explain.showReasoning": "দেখান",
  "explain.agreeOn": (p) =>
    `${Number(p.k)}টির মধ্যে ${Number(p.agreeing)}টি পুনরুদ্ধার করা কেস ${String(p.label) || "প্রধান ফাইন্ডিং"}-এ একমত`,
  "explain.grounding":
    "উত্তরগুলি পুনরুদ্ধার করা কেস এবং এই রিপোর্টের উপর ভিত্তি করে। সহকারী নতুন কোনো ফলাফল প্রবর্তন করতে পারে না, এবং এটি দ্বিতীয় মতামত নয়।",
  "explain.idlePrompt":
    "একটি গ্রাউন্ডেড উত্তর দেখতে এই রিপোর্ট সম্পর্কে একটি প্রশ্ন জিজ্ঞাসা করুন। প্রতিটি উত্তর কেবল পুনরুদ্ধার করা কেস এবং রিপোর্টের পাঠ্য থেকে নেওয়া হয়।",
  "explain.ariaAsk": "এই রিপোর্ট সম্পর্কে একটি প্রশ্ন জিজ্ঞাসা করুন",
  "explain.placeholder": "এই রিপোর্টের একটি বাক্য সম্পর্কে জিজ্ঞাসা করুন…",
  "explain.ask": "জিজ্ঞাসা করুন",
  "explain.reportImpression": "রিপোর্ট ইম্প্রেশন",
  "explain.casesInContext": "প্রসঙ্গে কেস",
  "explain.auditNote": "প্রশ্ন ও উত্তরগুলি রিপোর্টের অডিট ট্রেইলের অংশ হিসেবে থাকে।",

  // ── settings / profile ────────────────────────────────────────────────────
  "settings.signInToView": "সেটিংস দেখতে সাইন ইন করুন।",
  "settings.errLoadProfile": "প্রোফাইল লোড করা যায়নি।",
  "settings.errSave": "সংরক্ষণ করা যায়নি।",
  "settings.loading": "সেটিংস লোড হচ্ছে…",
  "settings.allSaved": "সমস্ত পরিবর্তন সংরক্ষিত",
  "settings.identityTitle": "পরিচয় ও স্বাক্ষর",
  "settings.identityDesc": "আপনার স্বাক্ষরিত প্রতিটি রিপোর্টের নিচে ছাপা হয়।",
  "settings.bmdcNumber": "BMDC নম্বর",
  "settings.bmdcNote": "যেমন প্রবেশ করানো হয়েছে তেমনই নথিভুক্ত। এই সিস্টেমের BMDC নিবন্ধনে কোনো প্রবেশাধিকার নেই এবং এটি যাচাই করতে পারে না।",
  "settings.sigPreview": "স্বাক্ষরিত রিপোর্টে যেভাবে দেখায়",
  "settings.defaultsTitle": "পঠন ডিফল্ট",
  "settings.defaultsDesc": "আপনার শুরু করা প্রতিটি নতুন পরীক্ষায় প্রয়োগ করা হয়।",
  "settings.defaultK": "ডিফল্ট K (পুনরুদ্ধার করা কেস)",
  "settings.defaultKNote": "মূল্যায়নে পাঁচটি ব্যবহার করা হয়েছিল। বেশি কেস মানে ধীর জেনারেশন।",
  "settings.defaultLanguage": "ডিফল্ট ভাষা",
  "settings.langEnglish": "ইংরেজি",
  "settings.langBangla": "বাংলা",
  "settings.skipQuestionnaire": "ডিফল্টভাবে প্রশ্নমালা এড়িয়ে যান",
  "settings.railState": "প্রমাণ রেল অবস্থা",
  "settings.expanded": "প্রসারিত",
  "settings.collapsed": "সংকুচিত",
  "settings.exportFormat": "রপ্তানি ফরম্যাট",
  "settings.exportNote": "কেবল একটি পছন্দ হিসেবে সংরক্ষিত। রপ্তানি (PDF ডাউনলোড) এখনও এই অ্যাপের কোথাও বাস্তবায়িত হয়নি।",
  "settings.saving": "সংরক্ষণ হচ্ছে…",
  "settings.saveChanges": "পরিবর্তন সংরক্ষণ করুন",
  "settings.savedShort": "সংরক্ষিত।",
  "settings.thisMachine": "এই মেশিন",
  "settings.localNote": "সবকিছু স্থানীয়ভাবে চলে। কিছুই ভবনের বাইরে যায় না।",
  "settings.backend": "ব্যাকএন্ড",
  "settings.checking": "যাচাই হচ্ছে…",
  "settings.statusOk": "ঠিক আছে",
  "settings.statusUnreachable": "পৌঁছানো যাচ্ছে না",
  "settings.indexSize": "ইনডেক্স আকার",
  "settings.embeddingModel": "এমবেডিং মডেল",
  "settings.maskedStored": "সংরক্ষিত মাস্কড ছবি",
  "settings.originalStored": "সংরক্ষিত মূল ছবি",
  "settings.casesValue": (p) => `${Number(p.count)}টি কেস`,
  "settings.phiNote": "সিস্টেম স্টোরেজ থেকে আনমাস্কড PHI প্রকাশ করতে পারে না, কারণ আনমাস্কড PHI কখনও সংরক্ষিত হয় না।",

  // ── report document fields + diff + finalize + editable section ────────────
  "report.examination": "পরীক্ষা",
  "report.clinicalHistory": "ক্লিনিক্যাল ইতিহাস",
  "report.technique": "কৌশল",
  "report.findings": "ফলাফল",
  "report.impression": "ইম্প্রেশন",
  "report.recommendation": "সুপারিশ",
  "report.disclaimer": "দাবিত্যাগ",
  "report.sectionsChanged": (p) => `${Number(p.total)}টির মধ্যে ${Number(p.changed)}টি সেকশন পরিবর্তিত`,
  "report.editedOfDraft": (p) => `এআই খসড়ার ${String(p.pct)}% সম্পাদিত হয়েছে`,
  "report.noEdits": "কোনো সম্পাদনা করা হয়নি।",
  "report.diffFooter":
    "মূল এআই খসড়ার সাথে বর্তমান রিপোর্টের তুলনা। এটি সামগ্রিকভাবে কী পরিবর্তিত হয়েছে তা দেখায়, ধাপে ধাপে সম্পাদনার ইতিহাস নয়।",
  "report.errFinalize": "রিপোর্ট চূড়ান্ত করা যায়নি।",
  "report.previewTitle": "চূড়ান্ত করার আগে প্রিভিউ",
  "report.previewDesc": "একবার চূড়ান্ত হলে, এই রিপোর্ট আর সম্পাদনা করা যাবে না।",
  "report.changesAi": "এআই খসড়ার তুলনায় পরিবর্তন",
  "report.hideChangesAi": "এআই খসড়ার তুলনায় পরিবর্তন লুকান",
  "report.backToEdit": "সম্পাদনায় ফিরে যান",
  "report.finalizing": "চূড়ান্ত হচ্ছে…",
  "report.confirmFinalize": "চূড়ান্ত নিশ্চিত করুন",
  "report.editedByDoctor": "ডাক্তার কর্তৃক সম্পাদিত",
  "report.editedAria": "সম্পাদিত",
  "report.edited": "সম্পাদিত",
  "report.saving": "সংরক্ষণ হচ্ছে…",
  "report.regenerating": "পুনরায় তৈরি হচ্ছে…",
  "report.regenerate": "পুনরায় তৈরি করুন",
  "report.edit": "সম্পাদনা",
  "report.candidateNotApplied": "পুনরায় তৈরি করা প্রার্থী, প্রয়োগ করা হয়নি",
  "report.contextIncomplete":
    "এই রিপোর্টটি সম্পূর্ণ প্রসঙ্গ ধারণের আগের। এই প্রার্থীটি কেবল পুনরুদ্ধার করা প্রমাণ থেকে তৈরি, তাই এটি মূল প্রশ্নমালার প্রসঙ্গ প্রতিফলিত নাও করতে পারে।",
  "report.accept": "গ্রহণ করুন",
  "report.discard": "বাতিল করুন",
  "report.discardNote": "বাতিল করলে কোনো অনুরোধ পাঠানো হয় না।",

  // ── status / ownership chips ──────────────────────────────────────────────
  "chip.statusDraft": "এআই খসড়া",
  "chip.statusReview": "পর্যালোচনাধীন",
  "chip.statusEdited": "ডাক্তার সম্পাদিত",
  "chip.statusFinal": "চূড়ান্ত",
  "chip.you": "আপনি",

  // ── evidence agreement ────────────────────────────────────────────────────
  "agreement.title": "প্রমাণের ঐকমত্য",
  "agreement.strong": "শক্তিশালী",
  "agreement.mixed": "মিশ্র",
  "agreement.weak": "দুর্বল",
  "agreement.agreeLine": (p) => `${Number(p.k)}টির মধ্যে ${Number(p.agreeing)}টি পুনরুদ্ধার করা কেস প্রাথমিক ফলাফলে একমত।`,
  "agreement.top1": "শীর্ষ-১ সাদৃশ্য",
  "agreement.meanSim": (p) => `গড় সাদৃশ্য (K=${Number(p.k)})`,
  "agreement.clinHistory": "ক্লিনিক্যাল ইতিহাস প্রদান করা হয়েছে",
  "agreement.notRecorded": "নথিভুক্ত নয়",
  "agreement.yes": "হ্যাঁ",
  "agreement.no": "না",
  "agreement.labelSpread": "লেবেল বিস্তার",
  "agreement.labelsCount": (p) => `${Number(p.count)}টি লেবেল`,
  "agreement.defPre": "পুনরুদ্ধার করা কেসগুলির মধ্যে ঐকমত্য পরিমাপ করে।",
  "agreement.defBold": "রিপোর্টটি সঠিক হওয়ার সম্ভাবনা নয়।",

  // Retrieval support -- PROVISIONAL, UNREVIEWED terminology, same caveat
  // as every other Bangla string in this project (report_formatter.py's
  // section headers, evidence_disclaimer.py's templates). Not to be
  // presented as clinically or linguistically validated without a domain
  // reviewer's sign-off.
  "support.title": "পুনরুদ্ধার সমর্থন",
  "support.atOrAbove": "পূরণ হয়েছে",
  "support.below": "সীমার নিচে",
  "support.notRecorded": "রেকর্ড করা হয়নি",
  "support.top1": "শীর্ষ-১ সাদৃশ্য",
  "support.def": "পুনরুদ্ধার করা কেসগুলি এই ছবির কতটা কাছাকাছি তা পরিমাপ করে।",
  // Projection rejection messages -- §10.1. PROVISIONAL, UNREVIEWED
  // terminology, the same caveat every other Bangla string in this project
  // carries. The second string keeps the doubt of the English M12 wording;
  // a translation that asserted the image was wrong would violate M12 in
  // one language while satisfying it in the other.
  // A14 -- PROVISIONAL, UNREVIEWED terminology, as with every Bangla
  // string in this project.
  "upload.projectionLabel": "প্রজেকশন (আবশ্যক)",
  "upload.projectionPA": "PA",
  "upload.projectionAP": "AP",
  "upload.projectionLATERAL": "ল্যাটারাল",
  "upload.projectionNote":
    "রিকুইজিশনে উল্লিখিত ভিউ নির্বাচন করুন। RadAssist ফ্রন্টাল বুকের এক্স-রে (PA বা AP) রিপোর্ট করে।",
  "error.projection.declaredLateral":
    "ফ্রন্টাল ভিউ প্রয়োজন। RadAssist ফ্রন্টাল বুকের এক্স-রে (PA বা AP) রিপোর্ট করে। অনুগ্রহ করে এই স্টাডির ফ্রন্টাল ছবিটি আপলোড করুন।",
  "error.projection.frontalMismatch":
    "এটি ফ্রন্টাল বুকের এক্স-রে বলে মনে হচ্ছে না। RadAssist শুধুমাত্র ফ্রন্টাল ভিউ (PA বা AP) রিপোর্ট করে। যদি এটি ফ্রন্টাল ছবি হয়, তবে এটি রেফারেন্স আর্কাইভ থেকে ভিন্ন হতে পারে। অনুগ্রহ করে ভিউটি পরীক্ষা করে আবার চেষ্টা করুন।",

  "support.belowNote":
    "কোনো পুনরুদ্ধার করা কেস ন্যূনতম সমর্থন সীমা পূরণ করে না। শুধুমাত্র ঐকমত্যের স্কোর শক্তিশালী প্রমাণ নির্দেশ করে না। এর অর্থ এই নয় যে অনুরূপ কোনো কেস নেই — শুধু এই যে পুনরুদ্ধার করা কেসগুলির কোনোটিই সীমা পূরণ করেনি।",

  // ── step progress ─────────────────────────────────────────────────────────
  "step.running": "চলছে",
  "step.skipped": "এড়ানো হয়েছে",

  // ── PHI reveal slider ─────────────────────────────────────────────────────
  "phi.altMasked": "মাস্ক করা বুকের এক্স-রে",
  "phi.altOriginal": "মাস্কিংয়ের আগের মূল বুকের এক্স-রে",
  "phi.ariaReveal": "মাস্ক করা কপির নিচে মূল ছবি প্রকাশ করুন",
  "phi.caption": "মাস্ক করা কপির নিচে মূলটি দেখাতে টেনে আনুন। মূলটি কেবল এই সেশন থেকে দেখানো হচ্ছে। সংরক্ষিত নয়।",
};
