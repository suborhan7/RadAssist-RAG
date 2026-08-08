<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet><meta name="design_doc_mode" content="canvas"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin=""><link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&amp;family=IBM+Plex+Mono:wght@400;500&amp;family=Noto+Sans+Bengali:wght@400;500&amp;display=swap" rel="stylesheet"><script src="./image-slot.js"></script><style>body{margin:0;background:#04070A;font-family:'Space Grotesk',system-ui,sans-serif;color:#E6EDF3;-webkit-font-smoothing:antialiased}a{color:#22E3E8}a:hover{color:#E6EDF3}@keyframes rr-flow{0%{transform:translateX(-100%)}100%{transform:translateX(320%)}}@keyframes rr-blink{0%,100%{opacity:.3}50%{opacity:1}}@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style></helmet>

<div style="padding:26px 30px 74px">

<div style="width:1440px;margin:0 auto 16px">
<div style="display:flex;align-items:baseline;gap:12px;margin-bottom:10px">
<span style="font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:#96A3B0">Reading Room · every screen</span>
<span style="font-size:13px;color:#8C9AA8">Cyan is retrieval and interaction. Amber is look-here. Nothing else is coloured.</span>
</div>
<div style="display:flex;flex-wrap:wrap;gap:5px">
<sc-for list="{{ screens }}" as="s" hint-placeholder-count="15">
<button type="button" onClick="{{ s.onClick }}" style="{{ s.btnStyle }}">{{ s.route }}</button>
</sc-for>
</div>
</div>

<div style="width:1440px;height:900px;margin:0 auto;background:#0A0D10;border:1px solid #1B2229;border-radius:10px;overflow:hidden;display:flex;position:relative;font-size:15px" data-screen-label="{{ screenLabel }}">

<sc-if value="{{ showRail }}" hint-placeholder-val="{{ true }}">
<div style="{{ railStyle }}">
<div style="{{ railHeaderStyle }}">
<span style="width:9px;height:9px;flex:none;border-radius:50%;background:#22E3E8;box-shadow:0 0 12px #22E3E8"></span>
<sc-if value="{{ railWide }}" hint-placeholder-val="{{ true }}">
<span style="font-size:15px;font-weight:600;letter-spacing:-.01em;flex:1">RadAssist</span>
</sc-if>
</div>
<div style="flex:1;overflow:auto;padding:14px 10px;display:flex;flex-direction:column;gap:3px">
<sc-for list="{{ railItems }}" as="r" hint-placeholder-count="7">
<button type="button" onClick="{{ r.onClick }}" style="{{ r.style }}"><span style="{{ r.glyphStyle }}">{{ r.glyph }}</span><span style="{{ r.labelStyle }}">{{ r.label }}</span></button>
</sc-for>
</div>
<div style="flex:none;border-top:1px solid #1B2229;padding:12px 10px">
<button type="button" onClick="{{ goSettings }}" style="{{ settingsStyle }}"><span style="{{ settingsGlyphStyle }}">◍</span><span style="{{ settingsLabelStyle }}">Settings</span></button>
<button type="button" onClick="{{ goLogout }}" style="{{ signOutStyle }}"><span style="{{ settingsGlyphStyle }}">→</span><span style="{{ settingsLabelStyle }}">Sign out</span></button>
<sc-if value="{{ railWide }}" hint-placeholder-val="{{ true }}">
<button type="button" onClick="{{ goSettings }}" title="Your profile" style="margin-top:10px;width:100%;border:none;background:transparent;border-top:1px solid #1B2229;padding:13px 10px 3px;display:flex;align-items:center;gap:11px;cursor:pointer;text-align:left" style-hover="background:#12181E">
<span style="width:32px;height:32px;flex:none;border-radius:50%;overflow:hidden;background:#1B2229;display:block;pointer-events:none"><image-slot id="rr-avatar" shape="circle" fit="cover" placeholder=" "></image-slot></span>
<span style="flex:1;min-width:0;display:flex;flex-direction:column;gap:2px">
<span style="font-size:13px;font-weight:500;color:#E6EDF3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">Dr. Sumaiya Rahman</span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#96A3B0;white-space:nowrap">BMDC A-41822</span>
</span>
</button>
</sc-if>
</div>
</div>
</sc-if>

<div style="flex:1;min-width:0;display:flex;flex-direction:column">

<sc-if value="{{ isLanding }}" hint-placeholder-val="{{ false }}">
<div style="flex:1;overflow:auto">
<div style="height:66px;display:flex;align-items:center;justify-content:space-between;padding:0 36px;border-bottom:1px solid #1B2229;position:sticky;top:0;background:rgba(10,13,16,.94);z-index:2">
<div style="display:flex;align-items:center;gap:11px"><span style="width:9px;height:9px;border-radius:50%;background:#22E3E8;box-shadow:0 0 12px #22E3E8"></span><span style="font-size:16px;font-weight:600;letter-spacing:-.01em">RadAssist</span></div>
<div style="display:flex;align-items:center;gap:26px">
<span style="font-size:14px;color:#8C9AA8">Grounding</span>
<span style="font-size:14px;color:#8C9AA8">Privacy</span>
<span style="font-size:14px;color:#8C9AA8">বাংলা</span>
<span style="font-size:14px;font-weight:600;background:#22E3E8;color:#04181A;border-radius:6px;padding:9px 18px;white-space:nowrap">Sign in</span>
</div>
</div>

<div style="padding:70px 36px 56px;max-width:1240px;margin:0 auto">
<div style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;letter-spacing:.18em;text-transform:uppercase;color:#22E3E8;margin-bottom:26px">Chest X-ray reporting · Bangladesh</div>

<p style="font-size:19px;line-height:1.6;color:#8C9AA8;margin:0 0 36px;max-width:52ch">RadAssist finds chest films the archive has already reported, drafts from them, and shows you all of them. You edit. You sign.</p>
<h1 style="font-size:62px;line-height:1.04;letter-spacing:-.03em;font-weight:600;margin:0 0 26px;max-width:19ch;text-wrap:pretty">Every sentence names the case it came from.</h1><div style="display:flex;align-items:center;gap:16px">
<span style="font-size:16px;font-weight:600;background:#22E3E8;color:#04181A;border-radius:8px;padding:14px 26px;white-space:nowrap">Request a demo</span>
<span style="font-size:15px;border:1px solid #2A343D;border-radius:8px;padding:13px 22px;white-space:nowrap">Sign in</span>
</div>
</div>

<div style="padding:0 36px 60px;max-width:1240px;margin:0 auto">
<div style="border:1px solid #1B2229;border-radius:12px;overflow:hidden;background:#0E1318">
<div style="display:flex;align-items:center;gap:12px;padding:13px 18px;border-bottom:1px solid #1B2229">
<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#22E3E8">ONE STUDY, START TO SIGNATURE</span>
<span style="flex:1"></span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#96A3B0;white-space:nowrap">14.8s TOTAL</span>
</div>
<div style="display:grid;grid-template-columns:340px 1fr 300px">
<div style="background:#000;min-height:330px;position:relative"><image-slot id="rr-hero-film" shape="rect" fit="contain" placeholder="masked PA film"></image-slot><div style="position:absolute;left:26%;top:58%;width:28%;height:22%;border:1.5px solid #FFB020;border-radius:4px;pointer-events:none"></div></div>
<div style="padding:26px 28px;border-left:1px solid #1B2229;border-right:1px solid #1B2229">
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.16em;color:#96A3B0;margin-bottom:18px">DRAFTED IMPRESSION</div>
<div style="font-size:23px;line-height:38px;font-weight:500;letter-spacing:-.01em">Left lower lobe airspace opacity, consistent with pneumonia in the appropriate clinical setting.<span style="font-family:'IBM Plex Mono',monospace;font-size:13px;color:#22E3E8;padding-left:5px;white-space:nowrap">01,02</span></div>
<div style="margin-top:26px;padding-top:18px;border-top:1px solid #1B2229;font-size:14px;line-height:1.6;color:#8C9AA8">The superscript is the product. Click it and the case that produced the sentence opens — findings, impression, similarity, film.</div>
</div>
<div style="padding:22px 20px;display:flex;flex-direction:column;gap:18px">
<div><div style="display:flex;align-items:baseline;gap:8px"><span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#22E3E8;white-space:nowrap">01</span><span style="font-family:'IBM Plex Mono',monospace;font-size:26px;font-weight:500;letter-spacing:-.03em;white-space:nowrap">91.2</span></div><div style="font-size:13.5px;color:#8C9AA8;margin-top:3px">CXR-2117 · LLL pneumonia</div></div>
<div><div style="display:flex;align-items:baseline;gap:8px"><span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#22E3E8;white-space:nowrap">02</span><span style="font-family:'IBM Plex Mono',monospace;font-size:26px;font-weight:500;letter-spacing:-.03em;white-space:nowrap">87.4</span></div><div style="font-size:13.5px;color:#8C9AA8;margin-top:3px">CXR-0884 · basal airspace disease</div></div>
<div><div style="display:flex;align-items:baseline;gap:8px"><span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#96A3B0;white-space:nowrap">03</span><span style="font-family:'IBM Plex Mono',monospace;font-size:26px;font-weight:500;letter-spacing:-.03em;color:#8C9AA8;white-space:nowrap">84.1</span></div><div style="font-size:13.5px;color:#8C9AA8;margin-top:3px">CXR-3390 · basal atelectasis</div></div>
</div>
</div>
</div>
</div>

<div style="padding:0 36px 60px;max-width:1240px;margin:0 auto;display:grid;grid-template-columns:repeat(3,1fr);gap:26px">
<div><div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#22E3E8;margin-bottom:14px">01 · CONTROL</div><h3 style="font-size:22px;font-weight:600;letter-spacing:-.015em;margin:0 0 10px">The radiologist signs</h3><p style="font-size:15px;line-height:1.65;color:#8C9AA8;margin:0">Every report is a draft until a doctor finalises it. Signing records who signed and how much they changed.</p></div>
<div><div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#22E3E8;margin-bottom:14px">02 · LOCAL</div><h3 style="font-size:22px;font-weight:600;letter-spacing:-.015em;margin:0 0 10px">One machine, your building</h3><p style="font-size:15px;line-height:1.65;color:#8C9AA8;margin:0">Embedding, retrieval and generation all run on the clinic's own GPU. No cloud, no per-report cost, no image leaves.</p></div>
<div><div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#22E3E8;margin-bottom:14px">03 · PRIVACY</div><h3 style="font-size:22px;font-weight:600;letter-spacing:-.015em;margin:0 0 10px">Masked before anything reads it</h3><p style="font-size:15px;line-height:1.65;color:#8C9AA8;margin:0">Burned-in patient text is blacked out before embedding. Unmasked PHI is never stored, so it can never be disclosed.</p></div>
</div>

<div style="padding:0 36px 60px;max-width:1240px;margin:0 auto">
<div style="border-top:1px solid #1B2229;border-bottom:1px solid #1B2229;padding:34px 0;display:grid;grid-template-columns:1fr 1fr;gap:44px;align-items:center">
<div>
<h3 style="font-size:26px;font-weight:600;letter-spacing:-.02em;margin:0 0 12px">The report your patient reads is in Bangla</h3>
<p style="font-size:15px;line-height:1.65;color:#8C9AA8;margin:0">A first-class report surface with its own leading and export — not a translate button.</p>
</div>
<div style="border-left:2px solid #22E3E8;padding-left:20px">
<div style="font-family:'Noto Sans Bengali',sans-serif;font-size:17px;line-height:34px">বাম ফুসফুসের নিম্নাংশে অস্বচ্ছতা দেখা যাচ্ছে, সম্ভবত নিউমোনিয়া। ক্লিনিক্যাল সহসম্পর্ক প্রয়োজন।</div>
</div>
</div>
<div style="display:flex;gap:46px;padding:34px 0 0">
<div><div style="font-family:'IBM Plex Mono',monospace;font-size:34px;font-weight:500;letter-spacing:-.03em;white-space:nowrap">2,460</div><div style="font-size:14px;color:#8C9AA8;margin-top:4px">archive cases indexed</div></div>
<div><div style="font-family:'IBM Plex Mono',monospace;font-size:34px;font-weight:500;letter-spacing:-.03em;white-space:nowrap">460</div><div style="font-size:14px;color:#8C9AA8;margin-top:4px">held-out studies evaluated</div></div>
<div><div style="font-family:'IBM Plex Mono',monospace;font-size:34px;font-weight:500;letter-spacing:-.03em;color:#22E3E8;white-space:nowrap">0</div><div style="font-size:14px;color:#8C9AA8;margin-top:4px">reports signed without a doctor</div></div>
<span style="flex:1"></span>
<div style="align-self:center"><span style="font-size:16px;font-weight:600;background:#22E3E8;color:#04181A;border-radius:8px;padding:14px 26px;white-space:nowrap">Request a demo</span></div>
</div>
<p style="font-size:13px;line-height:1.7;color:#96A3B0;margin:44px 0 0;text-align:center">Research prototype. Not for clinical use. Every report requires review by a qualified radiologist.<br>Brac University · Department of Computer Science and Engineering</p>
</div>
</div>
</sc-if>

<sc-if value="{{ isLogin }}" hint-placeholder-val="{{ false }}">
<div style="flex:1;display:flex;min-height:0">
<div style="flex:1;min-width:0;position:relative;background:#000;display:flex;flex-direction:column;justify-content:flex-end;padding:44px">
<div style="position:absolute;inset:0;opacity:.5"><image-slot id="rr-login-film" shape="rect" fit="cover" placeholder="masked chest film"></image-slot></div>
<div style="position:relative;max-width:34ch">
<h1 style="font-size:38px;line-height:1.1;letter-spacing:-.025em;font-weight:600;margin:0 0 16px">Retrieval-grounded chest X-ray reporting.</h1>
<p style="font-size:15px;line-height:1.65;color:#8C9AA8;margin:0">Every draft cites the cases it was grounded in. 0 reports have ever been finalised without a radiologist.</p>
</div>
</div>
<div style="width:560px;flex:none;border-left:1px solid #1B2229;display:flex;align-items:center;justify-content:center;padding:44px">
<div style="width:380px;display:flex;flex-direction:column;gap:26px">
<div>
<h2 style="font-size:28px;letter-spacing:-.02em;font-weight:600;margin:0">Sign in</h2>
<p style="font-size:14px;color:#8C9AA8;margin:7px 0 0"><br></p>
</div>
<div style="display:flex;flex-direction:column;gap:16px">
<label style="display:flex;flex-direction:column;gap:7px"><span style="font-size:13px;color:#8C9AA8">Email</span><span style="height:46px;border:1px solid #2A343D;border-radius:8px;display:flex;align-items:center;padding:0 14px;font-size:15px;background:#0E1318;white-space:nowrap">s.rahman@radassist.local</span></label>
<label style="display:flex;flex-direction:column;gap:7px"><span style="font-size:13px;color:#8C9AA8">Password</span><span style="height:46px;border:1px solid #22E3E8;border-radius:8px;display:flex;align-items:center;padding:0 14px;font-family:'IBM Plex Mono',monospace;font-size:15px;background:#0E1318;color:#8C9AA8;white-space:nowrap">••••••••••<span style="width:1px;height:18px;background:#22E3E8;margin-left:3px"></span></span></label>
<span style="height:46px;background:#22E3E8;color:#04181A;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:600;margin-top:4px">Sign in</span>
</div>

<p style="font-size:14px;color:#8C9AA8;margin:0;text-align:center">No account? <a href="#" style="text-decoration:none;border-bottom:1px solid #22E3E8">Register</a></p>
</div>
</div>
</div>
</sc-if>

<sc-if value="{{ isRegister }}" hint-placeholder-val="{{ false }}">
<div style="flex:1;display:flex;align-items:center;justify-content:center;padding:44px">
<div style="width:1000px;display:grid;grid-template-columns:1fr 330px;gap:44px;align-items:start">
<div>
<h2 style="font-size:32px;letter-spacing:-.025em;font-weight:600;margin:0 0 8px">Register a doctor account</h2>
<p style="font-size:15px;line-height:1.6;color:#8C9AA8;margin:0 0 30px;max-width:52ch">The patient registry is shared with your department. Your unsigned drafts are not.</p>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
<label style="display:flex;flex-direction:column;gap:7px;grid-column:1/-1"><span style="font-size:13px;color:#8C9AA8">Full name, as printed on reports</span><span style="height:46px;border:1px solid #2A343D;border-radius:8px;display:flex;align-items:center;padding:0 14px;font-size:15px;background:#0E1318;white-space:nowrap">Dr. Sumaiya Rahman</span></label>
<label style="display:flex;flex-direction:column;gap:7px"><span style="font-size:13px;color:#8C9AA8">Qualifications</span><span style="height:46px;border:1px solid #2A343D;border-radius:8px;display:flex;align-items:center;padding:0 14px;font-size:15px;background:#0E1318;white-space:nowrap">MBBS, FCPS (Radiology)</span></label>
<label style="display:flex;flex-direction:column;gap:7px"><span style="font-size:13px;color:#8C9AA8">BMDC number</span><span style="height:46px;border:1px solid #2A343D;border-radius:8px;display:flex;align-items:center;padding:0 14px;font-family:'IBM Plex Mono',monospace;font-size:15px;background:#0E1318;white-space:nowrap">A-41822</span></label>
<label style="display:flex;flex-direction:column;gap:7px"><span style="font-size:13px;color:#8C9AA8">Email</span><span style="height:46px;border:1px solid #2A343D;border-radius:8px;display:flex;align-items:center;padding:0 14px;font-size:15px;background:#0E1318;white-space:nowrap">s.rahman@radassist.local</span></label>
<label style="display:flex;flex-direction:column;gap:7px"><span style="font-size:13px;color:#8C9AA8">Password</span><span style="height:46px;border:1px solid #2A343D;border-radius:8px;display:flex;align-items:center;padding:0 14px;font-family:'IBM Plex Mono',monospace;font-size:15px;background:#0E1318;color:#8C9AA8;white-space:nowrap">••••••••••</span></label>
</div>
<div style="margin-top:22px;display:flex;align-items:center;gap:18px">
<span style="height:46px;background:#22E3E8;color:#04181A;border-radius:8px;display:inline-flex;align-items:center;padding:0 24px;font-size:15px;font-weight:600;white-space:nowrap">Create account</span>
<span style="font-size:14px;color:#8C9AA8">Already registered? <a href="#" style="text-decoration:none;border-bottom:1px solid #22E3E8">Sign in</a></span>
</div>
</div>
<div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0;margin-bottom:16px">SIGNATURE BLOCK · LIVE</div>
<div style="border:1px solid #1B2229;border-radius:10px;background:#0E1318;padding:22px 20px;white-space:nowrap">
<div style="border-top:2px solid #22E3E8;padding-top:14px">
<div style="font-size:17px;font-weight:500">Dr. Sumaiya Rahman</div>
<div style="font-size:14px;color:#8C9AA8;margin-top:3px">MBBS, FCPS (Radiology)</div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#96A3B0;margin-top:8px;white-space:nowrap">BMDC A-41822</div>
</div>
</div>
<p style="font-size:13.5px;line-height:1.65;color:#8C9AA8;margin:16px 0 0">Recorded as entered and printed on every report you sign. This system has no access to the BMDC registry and cannot verify it.</p>
</div>
</div>
</div>
</sc-if>

<sc-if value="{{ isDashboard }}" hint-placeholder-val="{{ false }}">
<div style="flex:none;height:60px;border-bottom:1px solid #1B2229;display:flex;align-items:center;padding:0 30px;gap:16px">
<h1 style="font-size:16px;font-weight:600;letter-spacing:-.01em;margin:0">Reading queue</h1>
<span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#96A3B0;white-space:nowrap">THU 31 JUL 2026 · 09:14</span>
<span style="flex:1"></span>
<span style="font-size:14px;color:#8C9AA8;border:1px solid #2A343D;border-radius:6px;padding:8px 14px;white-space:nowrap">Find patient</span>
<span style="font-size:14px;font-weight:600;background:#22E3E8;color:#04181A;border-radius:6px;padding:9px 16px;white-space:nowrap">New examination</span>
</div>
<div style="flex:1;overflow:auto;padding:34px 30px 30px">
<div style="display:flex;align-items:flex-end;gap:36px;margin-bottom:34px">
<div style="flex:1">
<h2 style="font-size:40px;line-height:1.1;letter-spacing:-.03em;font-weight:600;margin:0 0 14px">Three reports are waiting on you.</h2>
<div style="display:flex;align-items:center;gap:14px"><span style="font-size:15px;font-weight:600;background:#22E3E8;color:#04181A;border-radius:6px;padding:9px 18px;white-space:nowrap">Open the oldest</span><span style="font-size:14px;color:#FFB020">Rafiqul Islam · waiting 2 days</span></div>
</div>
<div style="display:flex;gap:34px;flex:none">
<div><div style="font-family:'IBM Plex Mono',monospace;font-size:30px;font-weight:500;letter-spacing:-.03em;white-space:nowrap">14</div><div style="font-size:13px;color:#8C9AA8;margin-top:3px">examinations today</div></div>
<div><div style="font-family:'IBM Plex Mono',monospace;font-size:30px;font-weight:500;letter-spacing:-.03em;white-space:nowrap">9</div><div style="font-size:13px;color:#8C9AA8;margin-top:3px">signed by you</div></div>
<div><div style="font-family:'IBM Plex Mono',monospace;font-size:30px;font-weight:500;letter-spacing:-.03em;white-space:nowrap">16%</div><div style="font-size:13px;color:#8C9AA8;margin-top:3px">median edit</div></div>
</div>
</div>

<div style="border-top:1px solid #1B2229">
<div style="display:grid;grid-template-columns:1.5fr 150px 130px 150px 100px 120px;gap:14px;padding:12px 4px;font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.14em;color:#96A3B0;border-bottom:1px solid #1B2229">
<span>PATIENT</span><span>STUDY</span><span>WAITING</span><span>STATUS</span><span>EDITED</span><span></span>
</div>
<sc-for list="{{ queue }}" as="q" hint-placeholder-count="5">
<div style="{{ q.rowStyle }}">
<div style="min-width:0"><div style="font-size:16px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ q.name }}</div><div style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:#96A3B0;margin-top:2px;white-space:nowrap">{{ q.code }}</div></div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#8C9AA8;white-space:nowrap">{{ q.study }}</div>
<div style="font-size:14px;color:{{ q.waitColor }}">{{ q.waiting }}</div>
<div><span style="{{ q.chipStyle }}">{{ q.status }}</span></div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:13px;color:#8C9AA8;white-space:nowrap">{{ q.edited }}</div>
<div style="text-align:right"><span style="{{ q.actionStyle }}">{{ q.action }}</span></div>
</div>
</sc-for>
</div>

<div style="margin-top:30px;display:flex;gap:36px;align-items:flex-start">
<p style="flex:1;font-size:14px;line-height:1.65;color:#8C9AA8;margin:0;max-width:56ch">You have reported on 128 of the hospital's 317 registered patients. You can open any colleague's patient; you cannot open their unsigned drafts.</p>

</div>
</div>
</sc-if>

<sc-if value="{{ isSearch }}" hint-placeholder-val="{{ false }}">
<div style="flex:none;height:60px;border-bottom:1px solid #1B2229;display:flex;align-items:center;padding:0 30px;gap:14px">
<span style="font-size:14px;color:#96A3B0">Queue</span><span style="color:#2A343D">/</span>
<h1 style="font-size:16px;font-weight:600;margin:0">Find patient</h1>
</div>
<div style="flex:1;overflow:auto;padding:34px 30px">
<div style="max-width:900px">
<div style="display:flex;gap:12px;margin-bottom:16px">
<span style="flex:1;height:56px;border:1px solid #22E3E8;border-radius:10px;display:flex;align-items:center;gap:12px;padding:0 18px;background:#0E1318;font-size:18px;white-space:nowrap">shahidul haq<span style="width:1px;height:22px;background:#22E3E8"></span></span>
<span style="height:56px;background:#22E3E8;color:#04181A;border-radius:10px;display:inline-flex;align-items:center;padding:0 26px;font-size:15px;font-weight:600;white-space:nowrap">Search</span>
</div>
<p style="font-size:14.5px;line-height:1.7;color:#8C9AA8;margin:0 0 34px;max-width:66ch">One field. A code, a name, or both. <span style="color:#E6EDF3">shahidul haq</span> also matched <span style="color:#E6EDF3">Shahidul Haque</span>, <span style="color:#E6EDF3">Shohidul Hoque</span> and <span style="color:#E6EDF3">Md. Shahidul Huq</span> — spelling is never the reason you can't find a patient.</p>

<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0;margin-bottom:6px">3 MATCHES</div>
<div style="border-top:1px solid #1B2229">
<sc-for list="{{ matches }}" as="m" hint-placeholder-count="3">
<div style="display:grid;grid-template-columns:1.5fr 150px 150px 1fr 90px;gap:18px;align-items:center;padding:18px 4px;border-bottom:1px solid #1B2229">
<div><div style="font-size:17px;font-weight:500">{{ m.name }}</div><div style="font-size:13px;color:#96A3B0;margin-top:2px">{{ m.alias }}</div></div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:12.5px;color:#8C9AA8;white-space:nowrap">{{ m.code }}</div>
<div style="font-size:14px;color:#8C9AA8">{{ m.dob }}</div>
<div style="min-width:0"><div style="font-size:13.5px;color:#8C9AA8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ m.last }}</div><div style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:#96A3B0;margin-top:2px;white-space:nowrap">{{ m.lastDate }}</div></div>
<div style="text-align:right"><span style="font-size:14px;color:#22E3E8;border:1px solid #2A343D;border-radius:6px;padding:7px 14px;white-space:nowrap">Open</span></div>
</div>
</sc-for>
</div>
<div style="margin-top:26px;display:flex;align-items:center;gap:20px">
<p style="flex:1;font-size:14px;line-height:1.65;color:#8C9AA8;margin:0;max-width:58ch">A well-formed search that finds nothing is not an error. Register the patient, or add a date of birth to narrow a common name.</p>
<span style="font-size:14px;font-weight:600;background:#22E3E8;color:#04181A;border-radius:6px;padding:10px 18px;flex:none;white-space:nowrap">Register new patient</span>
</div>
</div>
</div>
</sc-if>

<sc-if value="{{ isNewPatient }}" hint-placeholder-val="{{ false }}">
<div style="flex:none;height:60px;border-bottom:1px solid #1B2229;display:flex;align-items:center;padding:0 30px;gap:14px">
<span style="font-size:14px;color:#96A3B0">Find patient</span><span style="color:#2A343D">/</span>
<h1 style="font-size:16px;font-weight:600;margin:0">Register patient</h1>
</div>
<div style="flex:1;overflow:auto;padding:34px 30px">
<div style="max-width:960px;display:grid;grid-template-columns:1fr 320px;gap:44px;align-items:start">
<div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
<label style="display:flex;flex-direction:column;gap:7px;grid-column:1/-1"><span style="font-size:13px;color:#8C9AA8">Full name</span><span style="height:46px;border:1px solid #2A343D;border-radius:8px;display:flex;align-items:center;padding:0 14px;font-size:15px;background:#0E1318;white-space:nowrap">Ayesha Siddika</span></label>
<label style="display:flex;flex-direction:column;gap:7px"><span style="font-size:13px;color:#8C9AA8">Date of birth</span><span style="height:46px;border:1px solid #2A343D;border-radius:8px;display:flex;align-items:center;padding:0 14px;font-family:'IBM Plex Mono',monospace;font-size:15px;background:#0E1318;white-space:nowrap">12 Feb 1989</span></label>
<label style="display:flex;flex-direction:column;gap:7px"><span style="font-size:13px;color:#8C9AA8">Phone (optional)</span><span style="height:46px;border:1px solid #2A343D;border-radius:8px;display:flex;align-items:center;padding:0 14px;font-family:'IBM Plex Mono',monospace;font-size:15px;background:#0E1318;color:#8C9AA8;white-space:nowrap">01711 000000</span></label>
<div style="grid-column:1/-1;display:flex;flex-direction:column;gap:8px"><span style="font-size:13px;color:#8C9AA8">Sex</span><div style="display:flex;gap:9px"><span style="border:1px solid #22E3E8;background:rgba(34,227,232,.12);color:#22E3E8;border-radius:999px;padding:9px 20px;font-size:14px;white-space:nowrap">Female</span><span style="border:1px solid #2A343D;border-radius:999px;padding:9px 20px;font-size:14px;color:#8C9AA8;white-space:nowrap">Male</span><span style="border:1px solid #2A343D;border-radius:999px;padding:9px 20px;font-size:14px;color:#8C9AA8;white-space:nowrap">Other</span></div></div>
</div>
<div style="margin-top:26px;display:flex;gap:12px">
<span style="height:46px;background:#22E3E8;color:#04181A;border-radius:8px;display:inline-flex;align-items:center;padding:0 22px;font-size:15px;font-weight:600;white-space:nowrap">Register and start examination</span>
<span style="height:46px;border:1px solid #2A343D;border-radius:8px;display:inline-flex;align-items:center;padding:0 20px;font-size:15px;color:#8C9AA8;white-space:nowrap">Register only</span>
</div>
</div>
<div style="display:flex;flex-direction:column;gap:26px">
<div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0;margin-bottom:10px">WILL BE ASSIGNED</div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:30px;font-weight:500;letter-spacing:-.02em;white-space:nowrap">PAT-000318</div>
<p style="font-size:13.5px;line-height:1.6;color:#8C9AA8;margin:8px 0 0">Sequential and permanent. Written on the film envelope at reception.</p>
</div>
<div style="border:1px solid #FFB020;border-radius:10px;padding:18px 16px;background:rgba(255,176,32,.07);white-space:nowrap">
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.12em;color:#FFB020;margin-bottom:9px">POSSIBLE DUPLICATE</div>
<div style="font-size:14px;line-height:1.6;color:#E6EDF3">Ayesha Siddiqua, born 12 Feb 1989, is already registered as <span style="font-family:'IBM Plex Mono',monospace;font-size:13px;white-space:nowrap">PAT-000204</span>.</div>
<div style="margin-top:14px;display:flex;gap:9px"><span style="font-size:13px;font-weight:600;background:#FFB020;color:#1A1200;border-radius:6px;padding:8px 13px;white-space:nowrap">Open PAT-000204</span><span style="font-size:13px;border:1px solid #4A3A18;color:#FFB020;border-radius:6px;padding:8px 13px;white-space:nowrap">Different person</span></div>
</div>
</div>
</div>
</div>
</sc-if>

<sc-if value="{{ isPatient }}" hint-placeholder-val="{{ false }}">
<div style="flex:none;height:60px;border-bottom:1px solid #1B2229;display:flex;align-items:center;padding:0 30px;gap:14px">
<span style="font-size:14px;color:#96A3B0">Find patient</span><span style="color:#2A343D">/</span>
<h1 style="font-size:16px;font-weight:600;margin:0">Nasrin Akter</h1>
<span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#96A3B0;white-space:nowrap">PAT-000317</span>
<span style="flex:1"></span>
<span style="font-size:14px;color:#22E3E8;border:1px solid #2A343D;border-radius:6px;padding:8px 14px;white-space:nowrap">Compare 31 Jul with 12 Mar</span>
<span style="font-size:14px;font-weight:600;background:#22E3E8;color:#04181A;border-radius:6px;padding:9px 16px;white-space:nowrap">New examination</span>
</div>
<div style="flex:1;overflow:auto;padding:34px 30px">
<div style="max-width:1100px">
<div style="display:flex;align-items:flex-end;gap:44px;margin-bottom:34px">
<div><h2 style="font-size:34px;letter-spacing:-.025em;font-weight:600;margin:0">Nasrin Akter</h2><div style="font-size:15px;color:#8C9AA8;margin-top:6px">43 years · Female · born 04 Jan 1983</div></div>
<span style="flex:1"></span>
<div><div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0">ON RECORD</div><div style="font-size:17px;margin-top:4px">3 studies since Nov 2025</div></div>
</div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#22E3E8;margin-bottom:4px">PRIOR STUDIES · SAME PATIENT</div>
<div style="border-top:1px solid #1B2229">
<sc-for list="{{ priors }}" as="p" hint-placeholder-count="3">
<div style="{{ p.rowStyle }}">
<div style="width:88px;height:94px;flex:none;background:#000;border-radius:4px;overflow:hidden"><image-slot id="{{ p.slotId }}" shape="rect" fit="contain" placeholder="film"></image-slot></div>
<div style="flex:1;min-width:0">
<div style="display:flex;align-items:center;gap:14px;margin-bottom:8px">
<span style="font-family:'IBM Plex Mono',monospace;font-size:14px;font-weight:500;white-space:nowrap">{{ p.date }}</span>
<span style="font-size:13.5px;color:#96A3B0">{{ p.projection }}</span>
<span style="{{ p.chipStyle }}">{{ p.status }}</span>
<span style="{{ p.ownerStyle }}">{{ p.owner }}</span>
<span style="flex:1"></span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:#96A3B0;white-space:nowrap">{{ p.acc }}</span>
</div>
<div style="font-size:16px;line-height:1.6;max-width:74ch">{{ p.impression }}</div>
<div style="display:flex;gap:18px;margin-top:10px;align-items:center">
<span style="font-size:13.5px;color:#22E3E8">Open report</span>
<span style="{{ p.compareStyle }}">Compare with this</span>
<span style="font-size:13px;color:#96A3B0">{{ p.gap }}</span>
</div>
</div>
</div>
</sc-for>
</div>
<p style="font-size:13.5px;line-height:1.7;color:#8C9AA8;margin:24px 0 0;max-width:74ch">Prior studies are this patient over time. Archive cases — other patients' films retrieved by similarity — never appear here; they exist only inside the workspace.</p>
</div>
</div>
</sc-if>

<sc-if value="{{ isUpload }}" hint-placeholder-val="{{ false }}">
<div style="flex:none;height:60px;border-bottom:1px solid #1B2229;display:flex;align-items:center;padding:0 30px;gap:14px">
<span style="font-size:14px;color:#96A3B0">Nasrin Akter</span><span style="color:#2A343D">/</span>
<h1 style="font-size:16px;font-weight:600;margin:0">New examination</h1>
<span style="flex:1"></span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#96A3B0;white-space:nowrap">K=5 · EN · 14.8s ELAPSED</span>
</div>
<div style="flex:1;min-height:0;display:flex">
<div style="flex:1;min-width:0;background:#000;position:relative;display:flex;align-items:center;justify-content:center;padding:26px">
<div style="position:relative;width:100%;height:auto;max-width:100%;max-height:100%;aspect-ratio:1/1.04;flex:none;min-width:0"><image-slot id="rr-upload-film" shape="rect" fit="contain" placeholder="Drop the chest film"></image-slot>
<div style="position:absolute;top:12px;left:12px;width:126px;height:26px;background:#000;outline:1px dashed #22E3E8;pointer-events:none"></div>
<div style="position:absolute;top:0;bottom:0;left:58%;width:2px;background:#22E3E8;box-shadow:0 0 14px #22E3E8;pointer-events:none"><span style="position:absolute;top:50%;left:-16px;width:34px;height:34px;border-radius:50%;background:#22E3E8;color:#04181A;display:flex;align-items:center;justify-content:center;font-size:13px">↔</span></div>
</div>
<div style="position:absolute;left:26px;top:26px;font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.12em;color:#22E3E8">DRAG TO REVEAL THE ORIGINAL · 2 REGIONS MASKED</div>
<div style="position:absolute;left:26px;bottom:26px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:#96A3B0;white-space:nowrap">chest-31jul-0871.jpg · 2048 × 2130 · original never stored</div>
</div>
<div style="width:600px;flex:none;border-left:1px solid #1B2229;display:flex;flex-direction:column;min-height:0">
<div style="flex:none;padding:26px 28px 22px;border-bottom:1px solid #1B2229">
<h2 style="font-size:24px;letter-spacing:-.02em;font-weight:600;margin:0 0 18px">Running the pipeline</h2>
<div style="display:flex;flex-direction:column;gap:12px">
<sc-for list="{{ steps }}" as="k" hint-placeholder-count="5">
<div style="display:flex;align-items:center;gap:12px">
<span style="{{ k.iconStyle }}">{{ k.icon }}</span>
<span style="font-size:15px;flex:1;color:{{ k.textColor }}">{{ k.label }}</span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:12.5px;color:#96A3B0;white-space:nowrap">{{ k.time }}</span>
</div>
</sc-for>
</div>
<div style="height:2px;background:#1B2229;margin-top:18px;overflow:hidden"><div style="height:2px;width:32%;background:#22E3E8;animation:rr-flow 1.6s linear infinite"></div></div>
</div>
<div style="flex:1;overflow:auto;padding:24px 28px 28px">
<div style="display:flex;align-items:baseline;gap:12px;margin-bottom:12px">
<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#FFB020">RETRIEVAL WAS AMBIGUOUS</span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:#96A3B0;white-space:nowrap">TOP 71.4% · USUAL 84–93%</span>
</div>
<p style="font-size:15px;line-height:1.65;color:#8C9AA8;margin:0 0 20px">Three questions will narrow the retrieval before anything is drafted. Your answers go into the prompt and are kept with the report.</p>
<div style="display:flex;flex-direction:column;gap:18px">
<div><div style="font-size:15px;margin-bottom:9px">Duration of symptoms</div><div style="display:flex;gap:9px"><span style="border:1px solid #2A343D;border-radius:999px;padding:8px 16px;font-size:13.5px;color:#8C9AA8;white-space:nowrap">Under 1 week</span><span style="border:1px solid #22E3E8;background:rgba(34,227,232,.12);color:#22E3E8;border-radius:999px;padding:8px 16px;font-size:13.5px;white-space:nowrap">1–4 weeks</span><span style="border:1px solid #2A343D;border-radius:999px;padding:8px 16px;font-size:13.5px;color:#8C9AA8;white-space:nowrap">Over 4 weeks</span></div></div>
<div><div style="font-size:15px;margin-bottom:9px">Fever, weight loss or night sweats</div><div style="display:flex;gap:9px"><span style="border:1px solid #2A343D;border-radius:999px;padding:8px 22px;font-size:13.5px;color:#8C9AA8;white-space:nowrap">Yes</span><span style="border:1px solid #2A343D;border-radius:999px;padding:8px 22px;font-size:13.5px;color:#8C9AA8;white-space:nowrap">No</span></div></div>
<div><div style="font-size:15px;margin-bottom:9px">Known TB contact or prior treatment</div><div style="display:flex;gap:9px"><span style="border:1px solid #2A343D;border-radius:999px;padding:8px 22px;font-size:13.5px;color:#8C9AA8;white-space:nowrap">Yes</span><span style="border:1px solid #2A343D;border-radius:999px;padding:8px 22px;font-size:13.5px;color:#8C9AA8;white-space:nowrap">No</span></div></div>
</div>
<div style="margin-top:26px;display:flex;align-items:center;gap:12px">
<span style="font-size:15px;font-weight:600;background:#22E3E8;color:#04181A;border-radius:8px;padding:11px 18px;white-space:nowrap">Re-retrieve with answers</span>
<span style="font-size:14px;border:1px solid #2A343D;border-radius:8px;padding:11px 16px;color:#8C9AA8;white-space:nowrap">Skip and draft anyway</span>
</div>
<p style="font-size:13px;color:#96A3B0;margin:12px 0 0">Skipping is recorded on the report.</p>
</div>
</div>
</div>
</sc-if>

<sc-if value="{{ isWorkspace }}" hint-placeholder-val="{{ true }}">
<div style="flex:none;height:60px;border-bottom:1px solid #1B2229;display:flex;align-items:center;padding:0 24px;gap:16px">
<span style="font-size:15px;font-weight:600;letter-spacing:-.01em">Nasrin Akter</span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:#96A3B0;white-space:nowrap">PAT-000317 · ACC-2026-0871 · 31 JUL 2026</span>
<span style="flex:1"></span>
<span style="{{ diffToggleStyle }}">Changes vs draft</span>
<span style="{{ statusStyle }}">{{ statusLabel }}</span>
<span style="display:flex;border:1px solid #2A343D;border-radius:6px;overflow:hidden"><span style="{{ enTab }}">EN</span><span style="{{ bnTab }}">বাংলা</span></span>
<span style="font-size:14px;font-weight:600;background:#22E3E8;color:#04181A;border-radius:6px;padding:9px 18px;white-space:nowrap">Sign report</span>
</div>

<sc-if value="{{ showDiffPanel }}" hint-placeholder-val="{{ false }}">
<div style="flex:none;border-bottom:1px solid #1B2229;background:#0E1318;padding:24px 24px 26px;display:flex;gap:38px">
<div style="flex:none;width:250px">
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0;margin-bottom:12px">CHANGES VS AI DRAFT</div>
<div style="display:flex;align-items:baseline;gap:10px"><span style="font-family:'IBM Plex Mono',monospace;font-size:44px;font-weight:500;letter-spacing:-.04em;line-height:1">18.4</span><span style="font-size:20px;color:#8C9AA8">%</span></div>
<div style="font-size:14px;color:#8C9AA8;margin-top:8px">of drafted words changed · 4 of 5 sections</div>
<p style="font-size:13px;line-height:1.6;color:#96A3B0;margin:14px 0 0">Word-level against the immutable draft. The evaluation metric, not a score of the doctor.</p>
</div>
<div style="flex:1;min-width:0">
<div style="display:flex;gap:20px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:#96A3B0;margin-bottom:14px;white-space:nowrap"><span><span style="text-decoration:line-through">STRUCK</span> = DRAFTED, REMOVED</span><span style="color:#22E3E8;border-bottom:1px solid #22E3E8">UNDERLINED = YOUR WORDS</span></div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.14em;color:#96A3B0;margin-bottom:8px">FINDINGS · 3 EDITS</div>
<div style="font-size:16px;line-height:30px">The heart size and mediastinal contours are within normal limits. There is <span style="color:#61707E;text-decoration:line-through">patchy</span> <span style="color:#22E3E8;border-bottom:1px solid #22E3E8">ill-defined</span> airspace opacity in the left lower lobe<span style="color:#22E3E8;border-bottom:1px solid #22E3E8">, with air bronchograms</span>. No pleural effusion or pneumothorax is identified. <span style="color:#61707E;text-decoration:line-through">The visualized bony structures are unremarkable.</span> <span style="color:#22E3E8;border-bottom:1px solid #22E3E8">Mild degenerative change of the thoracic spine.</span></div>
</div>
</div>
</sc-if>

<div style="flex:1;min-height:0;display:flex">
<div style="flex:1;min-width:0;background:#000;position:relative;display:flex;align-items:center;justify-content:center;padding:26px">
<div style="position:relative;width:100%;height:auto;max-width:100%;max-height:100%;aspect-ratio:1/1.04;flex:none;min-width:0"><image-slot id="rr-ws-film" shape="rect" fit="contain" placeholder="Drop the masked PA film"></image-slot>
<div style="position:absolute;top:12px;left:12px;width:126px;height:26px;background:#000;outline:1px dashed #22E3E8;pointer-events:none"></div>
<div style="position:absolute;top:14px;left:146px;font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.12em;color:#22E3E8;pointer-events:none">PHI MASKED</div>
<div style="position:absolute;left:29%;top:60%;width:25%;height:20%;border:1.5px solid #FFB020;border-radius:3px;pointer-events:none"><span style="position:absolute;bottom:-23px;left:0;font-family:'IBM Plex Mono',monospace;font-size:11px;color:#FFB020;white-space:nowrap">LLL opacity · cases 01,02</span></div>
</div>
<div style="position:absolute;left:26px;bottom:26px;display:flex;gap:9px;align-items:center">
<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#22E3E8;border:1px solid #1B2229;border-radius:5px;padding:6px 11px;background:#0A0D10;white-space:nowrap">MASK ON</span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#8C9AA8;border:1px solid #1B2229;border-radius:5px;padding:6px 11px;background:#0A0D10;white-space:nowrap">W/L</span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#8C9AA8;border:1px solid #1B2229;border-radius:5px;padding:6px 11px;background:#0A0D10;white-space:nowrap">INVERT</span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#8C9AA8;border:1px solid #1B2229;border-radius:5px;padding:6px 11px;background:#0A0D10;white-space:nowrap">PRIOR 12 MAR</span>
</div>
</div>

<div style="width:530px;flex:none;border-left:1px solid #1B2229;display:flex;flex-direction:column;min-height:0">
<div style="flex:1;overflow:auto;padding:26px 26px 0">
<div style="display:flex;align-items:baseline;gap:12px;margin-bottom:20px">
<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.16em;color:#96A3B0">{{ reportKicker }}</span>
<span style="flex:1"></span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#22E3E8;white-space:nowrap">REGENERATE</span>
</div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.16em;color:#96A3B0;margin-bottom:16px">FINDINGS</div>
<div style="display:flex;flex-direction:column;gap:16px">
<sc-for list="{{ clauses }}" as="c" hint-placeholder-count="4">
<div style="display:flex;gap:14px">
<span style="{{ c.supStyle }}">{{ c.sup }}</span>
<div style="{{ c.textStyle }}">{{ c.text }}<span style="{{ c.tagStyle }}">{{ c.tag }}</span></div>
</div>
</sc-for>
</div>

<sc-if value="{{ isRegen }}" hint-placeholder-val="{{ false }}">
<div style="margin-top:20px;border:1px solid #22E3E8;border-radius:10px;overflow:hidden">
<div style="background:rgba(34,227,232,.12);padding:9px 14px;display:flex;align-items:center;gap:12px">
<span style="font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.14em;color:#22E3E8">CANDIDATE · NOT APPLIED</span>
<span style="flex:1"></span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#96A3B0;white-space:nowrap">6.8s · SAME 3 CASES</span>
</div>
<div style="padding:16px 14px">
<div style="font-size:15px;line-height:28px;color:#61707E;text-decoration:line-through;margin-bottom:12px">There is patchy airspace opacity in the left lower lobe.</div>
<div style="font-size:16px;line-height:29px">There is ill-defined airspace opacity in the left lower lobe with associated <span style="color:#22E3E8;border-bottom:1px solid #22E3E8">air bronchograms</span>, without volume loss.<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#22E3E8;padding-left:4px;white-space:nowrap">01,02</span></div>
<div style="margin-top:18px;display:flex;align-items:center;gap:10px">
<span style="font-size:14px;font-weight:600;background:#22E3E8;color:#04181A;border-radius:6px;padding:8px 16px;white-space:nowrap">Accept</span>
<span style="font-size:14px;border:1px solid #2A343D;border-radius:6px;padding:8px 16px;color:#8C9AA8;white-space:nowrap">Discard</span>
<span style="flex:1"></span>
<span style="font-size:13px;color:#96A3B0">Discarding fires no request.</span>
</div>
</div>
</div>
</sc-if>

<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.16em;color:#96A3B0;margin:28px 0 14px">IMPRESSION</div>
<div style="display:flex;gap:14px">
<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#22E3E8;padding-top:8px;flex:none;width:38px;white-space:nowrap">01,02</span>
<div style="{{ impressionStyle }}">{{ txImpression }}</div>
</div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.16em;color:#96A3B0;margin:28px 0 14px">RECOMMENDATION</div>
<div style="display:flex;gap:14px">
<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#FFB020;padding-top:7px;flex:none;width:38px;white-space:nowrap">—</span>
<div style="{{ recStyle }}">{{ txRec }}</div>
</div>
<div style="margin:26px 0 0;padding:16px 0 26px;border-top:1px solid #1B2229;font-size:13.5px;line-height:1.65;color:#96A3B0">Drafted from 3 archive cases, then reviewed, edited and signed by the reporting radiologist. Not an autonomous diagnosis.</div>
</div>
<div style="flex:none;border-top:1px solid #1B2229;padding:16px 26px;display:flex;align-items:center;gap:14px">
<span style="width:8px;height:8px;border-radius:50%;background:#FFB020;flex:none"></span>
<span style="font-size:14px;color:#E6EDF3;flex:1">Recommendation has no supporting case — it is yours alone.</span>
<span style="font-size:13.5px;color:#22E3E8">Explain</span>
</div>
</div>

<div style="width:340px;flex:none;border-left:1px solid #1B2229;display:flex;flex-direction:column;min-height:0;background:#0E1318">
<div style="flex:none;display:flex;border-bottom:1px solid #1B2229">
<sc-for list="{{ railTabs }}" as="t" hint-placeholder-count="3">
<button type="button" onClick="{{ t.onClick }}" style="{{ t.style }}">{{ t.label }}</button>
</sc-for>
</div>

<sc-if value="{{ tabEvidence }}" hint-placeholder-val="{{ true }}">
<div style="flex:1;overflow:auto;padding:22px 20px 24px">
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0;margin-bottom:20px">ARCHIVE CASES · OTHER PATIENTS</div>
<div style="display:flex;flex-direction:column;gap:22px">
<sc-for list="{{ cases }}" as="c" hint-placeholder-count="3">
<div style="display:flex;gap:14px;align-items:flex-start">
<div style="width:72px;height:80px;flex:none;background:#000;border-radius:4px;overflow:hidden"><image-slot id="{{ c.slotId }}" shape="rect" fit="contain" placeholder="film"></image-slot></div>
<div style="flex:1;min-width:0">
<div style="display:flex;align-items:baseline;gap:8px"><span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#22E3E8;white-space:nowrap">{{ c.sup }}</span><span style="{{ c.numStyle }}">{{ c.num }}</span><span style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:#96A3B0;white-space:nowrap">{{ c.id }}</span></div>
<div style="font-size:14px;line-height:1.55;color:#8C9AA8;margin-top:5px">{{ c.impression }}</div>
<div style="font-size:12.5px;color:#96A3B0;margin-top:6px">{{ c.cites }}</div>
</div>
</div>
</sc-for>
<div style="border-top:1px solid #1B2229;padding-top:18px;display:flex;flex-direction:column;gap:10px">
<div style="display:flex;align-items:baseline;gap:10px"><span style="font-family:'IBM Plex Mono',monospace;font-size:15px;color:#8C9AA8;white-space:nowrap">83.6</span><span style="font-size:13.5px;color:#96A3B0">CXR-0233 · not cited</span></div>
<div style="display:flex;align-items:baseline;gap:10px"><span style="font-family:'IBM Plex Mono',monospace;font-size:15px;color:#8C9AA8;white-space:nowrap">82.9</span><span style="font-size:13.5px;color:#96A3B0">CXR-1507 · not cited</span></div>
<p style="font-size:13px;line-height:1.6;color:#96A3B0;margin:6px 0 0">Retrieved but not used by the draft. Still here to disagree with.</p>
</div>
</div>
</div>
</sc-if>

<sc-if value="{{ tabAgreement }}" hint-placeholder-val="{{ false }}">
<div style="flex:1;overflow:auto;padding:22px 20px">
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0;margin-bottom:14px">EVIDENCE AGREEMENT</div>
<div style="font-size:34px;font-weight:600;letter-spacing:-.025em;color:#22E3E8;margin-bottom:8px">Strong</div>
<p style="font-size:15px;line-height:1.6;color:#8C9AA8;margin:0 0 22px">3 of 5 retrieved cases agree on the primary finding.</p>
<div style="border-top:1px solid #1B2229">
<div style="display:flex;align-items:center;padding:12px 0;border-bottom:1px solid #1B2229"><span style="font-size:14px;color:#8C9AA8">Top-1 similarity</span><span style="flex:1"></span><span style="font-family:'IBM Plex Mono',monospace;font-size:14px;white-space:nowrap">91.2%</span></div>
<div style="display:flex;align-items:center;padding:12px 0;border-bottom:1px solid #1B2229"><span style="font-size:14px;color:#8C9AA8">Mean similarity (K=5)</span><span style="flex:1"></span><span style="font-family:'IBM Plex Mono',monospace;font-size:14px;white-space:nowrap">85.8%</span></div>
<div style="display:flex;align-items:center;padding:12px 0;border-bottom:1px solid #1B2229"><span style="font-size:14px;color:#8C9AA8">Clinical history provided</span><span style="flex:1"></span><span style="font-family:'IBM Plex Mono',monospace;font-size:14px;color:#22E3E8;white-space:nowrap">Yes</span></div>
<div style="display:flex;align-items:center;padding:12px 0"><span style="font-size:14px;color:#8C9AA8">Label spread</span><span style="flex:1"></span><span style="font-family:'IBM Plex Mono',monospace;font-size:14px;white-space:nowrap">4 labels</span></div>
</div>
<p style="font-size:14px;line-height:1.6;color:#8C9AA8;margin:22px 0 0">Measures agreement among retrieved cases. <span style="color:#E6EDF3">Not a probability that the report is correct.</span></p>
</div>
</sc-if>

<sc-if value="{{ tabAlternatives }}" hint-placeholder-val="{{ false }}">
<div style="flex:1;overflow:auto;padding:22px 20px">
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0;margin-bottom:18px">PRESENT IN THE RETRIEVED SET</div>
<div style="border-top:1px solid #1B2229">
<sc-for list="{{ altLabels }}" as="a" hint-placeholder-count="5">
<div style="display:flex;align-items:center;gap:12px;padding:13px 0;border-bottom:1px solid #1B2229">
<span style="font-size:15px;color:{{ a.color }}">{{ a.label }}</span>
<span style="flex:1"></span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:13px;color:#8C9AA8;white-space:nowrap">{{ a.count }}</span>
</div>
</sc-for>
</div>
<p style="font-size:14px;line-height:1.65;color:#8C9AA8;margin:20px 0 0">Absence means no retrieved case carried the label. <span style="color:#E6EDF3">It is not an exclusion.</span></p>
<div style="margin-top:20px;border:1px solid #2A343D;border-radius:8px;padding:14px;display:flex;align-items:center;gap:12px;white-space:nowrap"><span style="font-size:14px;flex:1">Ask why a label is missing</span><span style="font-size:13px;color:#22E3E8;border:1px solid #2A343D;border-radius:999px;padding:6px 12px;white-space:nowrap">Why not TB?</span></div>
</div>
</sc-if>
</div>
</div>

<sc-if value="{{ isFinalize }}" hint-placeholder-val="{{ false }}">
<div style="position:absolute;inset:0;background:rgba(4,7,10,.72);display:flex;align-items:center;justify-content:center;padding:50px">
<div style="width:900px;max-height:100%;background:#0E1318;border:1px solid #2A343D;border-radius:12px;display:flex;flex-direction:column;overflow:hidden">
<div style="flex:none;padding:20px 26px;border-bottom:1px solid #1B2229;display:flex;align-items:baseline;gap:14px">
<h2 style="font-size:24px;letter-spacing:-.02em;font-weight:600;margin:0">Sign this report</h2>
<span style="font-size:14px;color:#8C9AA8">Your name goes on it. After signing, the text is locked.</span>
<span style="flex:1"></span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#96A3B0;white-space:nowrap">ESC TO CANCEL</span>
</div>
<div style="flex:1;min-height:0;display:grid;grid-template-columns:1fr 300px">
<div style="overflow:auto;padding:26px 28px">
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0;margin-bottom:16px">ACC-2026-0871 · PAT-000317 · CHEST X-RAY, PA</div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.14em;color:#96A3B0;margin-bottom:8px">FINDINGS</div>
<div style="font-size:16px;line-height:30px;margin-bottom:22px">The heart size and mediastinal contours are within normal limits. There is ill-defined airspace opacity in the left lower lobe, with air bronchograms and no significant volume loss. No pleural effusion or pneumothorax is identified. Mild degenerative change of the thoracic spine.</div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.14em;color:#96A3B0;margin-bottom:8px">IMPRESSION</div>
<div style="font-size:19px;line-height:33px;font-weight:500;margin-bottom:22px">Left lower lobe airspace opacity, consistent with pneumonia in the appropriate clinical setting. Clinical correlation recommended.</div>
<div style="border-top:1px solid #1B2229;padding-top:18px;display:flex;justify-content:space-between;align-items:flex-end">
<div><div style="font-size:16px;font-weight:500">Dr. Sumaiya Rahman</div><div style="font-size:14px;color:#8C9AA8;margin-top:2px">MBBS, FCPS (Radiology)</div><div style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#96A3B0;margin-top:6px;white-space:nowrap">BMDC A-41822</div></div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:#96A3B0;text-align:right;white-space:nowrap">31 JUL 2026 · 09:34<br>3 CASES RECORDED</div>
</div>
</div>
<div style="overflow:auto;padding:24px 22px;border-left:1px solid #1B2229;display:flex;flex-direction:column;gap:22px">
<div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0;margin-bottom:14px">BEFORE YOU SIGN</div>
<div style="display:flex;flex-direction:column;gap:12px">
<div style="display:flex;gap:11px;align-items:flex-start"><span style="color:#22E3E8;font-size:14px">✓</span><span style="font-size:14px;flex:1">Impression present</span></div>
<div style="display:flex;gap:11px;align-items:flex-start"><span style="color:#22E3E8;font-size:14px">✓</span><span style="font-size:14px;flex:1">PHI masking confirmed</span></div>
<div style="display:flex;gap:11px;align-items:flex-start"><span style="color:#22E3E8;font-size:14px">✓</span><span style="font-size:14px;flex:1">Every section reviewed</span></div>
<div style="display:flex;gap:11px;align-items:flex-start"><span style="color:#FFB020;font-size:14px">!</span><span style="font-size:14px;flex:1;color:#FFB020">Follow-up interval is yours — no case behind it</span></div>
</div>
</div>
<div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0;margin-bottom:12px">RECORDED WITH YOUR SIGNATURE</div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:12.5px;line-height:2;color:#8C9AA8">edit 18.4%<br>sections amended 4 of 5<br>review time 21 min<br>cases cited 3 of 5</div>
</div>
<div style="margin-top:auto;display:flex;flex-direction:column;gap:10px">
<span style="height:46px;background:#22E3E8;color:#04181A;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:600">Sign and lock</span>
<span style="height:46px;border:1px solid #2A343D;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:15px;color:#8C9AA8">Keep editing</span>
</div>
</div>
</div>
</div>
</div>
</sc-if>
</sc-if>

<sc-if value="{{ isExplain }}" hint-placeholder-val="{{ false }}">
<div style="flex:none;height:60px;border-bottom:1px solid #1B2229;display:flex;align-items:center;padding:0 30px;gap:14px">
<span style="font-size:14px;color:#96A3B0">Workspace · ACC-2026-0871</span><span style="color:#2A343D">/</span>
<h1 style="font-size:16px;font-weight:600;margin:0">Explainability</h1>
<span style="flex:1"></span>
<span style="font-size:14px;color:#22E3E8">Back to workspace</span>
</div>
<div style="flex:1;min-height:0;display:flex">
<div style="flex:1;min-width:0;display:flex;flex-direction:column">
<div style="flex:none;padding:16px 30px;border-bottom:1px solid #1B2229;font-size:14px;line-height:1.6;color:#22E3E8">Answers are grounded in the retrieved cases and this report. The assistant cannot introduce new findings, and it is not a second opinion.</div>
<div style="flex:1;overflow:auto;padding:30px">
<div style="max-width:70ch;display:flex;flex-direction:column;gap:36px">
<div>
<div style="display:flex;align-items:baseline;gap:14px;border-bottom:1px solid #2A343D;padding-bottom:10px;margin-bottom:16px"><span style="font-size:22px;font-weight:600;letter-spacing:-.015em">Why not TB?</span><span style="flex:1"></span><span style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:#96A3B0;white-space:nowrap">09:21 · 1.9s</span></div>
<p style="font-size:17px;line-height:31px;margin:0 0 14px">None of the five retrieved cases carries a TB-associated label, and no upper-zone or cavitary pattern appears in any of them. The retrieval is dominated by lower-zone opacity cases. This is an absence of retrieved evidence — not an exclusion of the diagnosis, and not a reason to drop TB from your differential if the history supports it.</p>
<div style="display:flex;gap:10px;flex-wrap:wrap"><span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#22E3E8;border:1px solid #1B2229;border-radius:5px;padding:5px 10px;white-space:nowrap">01 CXR-2117 · 91.2%</span><span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#22E3E8;border:1px solid #1B2229;border-radius:5px;padding:5px 10px;white-space:nowrap">02 CXR-0884 · 87.4%</span></div>
</div>
<div>
<div style="display:flex;align-items:baseline;gap:14px;border-bottom:1px solid #2A343D;padding-bottom:10px;margin-bottom:16px"><span style="font-size:22px;font-weight:600;letter-spacing:-.015em">Which case drove the impression?</span><span style="flex:1"></span><span style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:#96A3B0;white-space:nowrap">09:19 · 2.3s</span></div>
<p style="font-size:17px;line-height:31px;margin:0 0 14px">CXR-2117, the closest match at 91.2%, reports left lower lobe pneumonia and supplied both the location and the word "pneumonia". CXR-3390 describes atelectasis rather than infection and pulled against that reading — it is the case to open if you disagree.</p>
<div style="display:flex;gap:10px;flex-wrap:wrap"><span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#22E3E8;border:1px solid #1B2229;border-radius:5px;padding:5px 10px;white-space:nowrap">01 CXR-2117 · 91.2%</span><span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#8C9AA8;border:1px solid #1B2229;border-radius:5px;padding:5px 10px;white-space:nowrap">03 CXR-3390 · 84.1%</span></div>
</div>
</div>
</div>
<div style="flex:none;border-top:1px solid #1B2229;padding:18px 30px">
<div style="display:flex;gap:9px;flex-wrap:wrap;margin-bottom:14px">
<span style="font-size:13.5px;color:#8C9AA8;border:1px solid #2A343D;border-radius:999px;padding:7px 14px;white-space:nowrap">Why pneumonia?</span>
<span style="font-size:13.5px;color:#8C9AA8;border:1px solid #2A343D;border-radius:999px;padding:7px 14px;white-space:nowrap">Why is cardiomegaly not mentioned?</span>
<span style="font-size:13.5px;color:#8C9AA8;border:1px solid #2A343D;border-radius:999px;padding:7px 14px;white-space:nowrap">What would change this impression?</span>
</div>
<div style="display:flex;gap:12px">
<span style="flex:1;height:48px;border:1px solid #2A343D;border-radius:8px;display:flex;align-items:center;padding:0 16px;font-size:15px;color:#96A3B0;background:#0E1318;white-space:nowrap">Ask about a sentence in this report…</span>
<span style="height:48px;background:#22E3E8;color:#04181A;border-radius:8px;display:inline-flex;align-items:center;padding:0 24px;font-size:15px;font-weight:600;white-space:nowrap">Ask</span>
</div>
</div>
</div>
<div style="width:330px;flex:none;border-left:1px solid #1B2229;background:#0E1318;padding:24px 22px;overflow:auto">
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0;margin-bottom:14px">THE SENTENCE IN QUESTION</div>
<div style="border-left:2px solid #22E3E8;padding-left:16px;font-size:16px;line-height:29px;margin-bottom:28px">Left lower lobe airspace opacity, consistent with pneumonia in the appropriate clinical setting.</div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0;margin-bottom:16px">CASES IN CONTEXT</div>
<div style="display:flex;flex-direction:column;gap:16px">
<div style="display:flex;gap:12px;align-items:center"><span style="width:46px;height:52px;background:#000;border-radius:4px;flex:none;overflow:hidden"><image-slot id="rr-ex-c1" shape="rect" fit="contain" placeholder="film"></image-slot></span><div style="flex:1;min-width:0"><div style="font-family:'IBM Plex Mono',monospace;font-size:13px;white-space:nowrap">91.2 · CXR-2117</div><div style="font-size:13px;color:#8C9AA8;margin-top:2px">LLL pneumonia</div></div></div>
<div style="display:flex;gap:12px;align-items:center"><span style="width:46px;height:52px;background:#000;border-radius:4px;flex:none;overflow:hidden"><image-slot id="rr-ex-c2" shape="rect" fit="contain" placeholder="film"></image-slot></span><div style="flex:1;min-width:0"><div style="font-family:'IBM Plex Mono',monospace;font-size:13px;white-space:nowrap">87.4 · CXR-0884</div><div style="font-size:13px;color:#8C9AA8;margin-top:2px">Basal airspace disease</div></div></div>
<div style="display:flex;gap:12px;align-items:center"><span style="width:46px;height:52px;background:#000;border-radius:4px;flex:none;overflow:hidden"><image-slot id="rr-ex-c3" shape="rect" fit="contain" placeholder="film"></image-slot></span><div style="flex:1;min-width:0"><div style="font-family:'IBM Plex Mono',monospace;font-size:13px;white-space:nowrap">84.1 · CXR-3390</div><div style="font-size:13px;color:#8C9AA8;margin-top:2px">Basal atelectasis</div></div></div>
</div>
<p style="font-size:13px;line-height:1.65;color:#96A3B0;margin:24px 0 0">Questions and answers stay with the report as part of its audit trail.</p>
</div>
</div>
</sc-if>

<sc-if value="{{ isCompare }}" hint-placeholder-val="{{ false }}">
<div style="flex:none;height:60px;border-bottom:1px solid #1B2229;display:flex;align-items:center;padding:0 30px;gap:14px">
<span style="font-size:14px;color:#96A3B0">Workspace</span><span style="color:#2A343D">/</span>
<h1 style="font-size:16px;font-weight:600;margin:0">Compare</h1>
<span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#96A3B0;white-space:nowrap">NASRIN AKTER · 141 DAYS APART</span>
<span style="flex:1"></span>
<span style="font-size:14px;color:#8C9AA8">Linked pan &amp; zoom</span>
<span style="width:38px;height:20px;border-radius:999px;background:#22E3E8;position:relative;flex:none"><span style="position:absolute;top:2px;right:2px;width:16px;height:16px;border-radius:50%;background:#04181A"></span></span>
</div>
<div style="flex:1;min-height:0;display:flex;flex-direction:column">
<div style="flex:1;min-height:0;display:grid;grid-template-columns:1fr 1fr">
<div style="display:flex;flex-direction:column;min-height:0;border-right:1px solid #1B2229">
<div style="flex:none;padding:14px 22px;display:flex;align-items:center;gap:12px;border-bottom:1px solid #1B2229"><span style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0">PRIOR · 12 MAR 2026 · PA</span><span style="flex:1"></span><span style="font-size:12.5px;color:#8C9AA8;border:1px solid #1B2229;border-radius:999px;padding:3px 10px;white-space:nowrap">Dr. Haque</span></div>
<div style="flex:none;height:300px;background:#000"><image-slot id="rr-cmp-prior" shape="rect" fit="contain" placeholder="prior film"></image-slot></div>
<div style="flex:1;overflow:auto;padding:20px 22px">
<div style="font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.14em;color:#96A3B0;margin-bottom:8px">IMPRESSION</div>
<div style="font-size:17px;line-height:30px;color:#8C9AA8">No acute cardiopulmonary abnormality.</div>
</div>
</div>
<div style="display:flex;flex-direction:column;min-height:0">
<div style="flex:none;padding:14px 22px;display:flex;align-items:center;gap:12px;border-bottom:1px solid #1B2229"><span style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#22E3E8">THIS STUDY · 31 JUL 2026 · PA</span><span style="flex:1"></span><span style="font-size:12.5px;color:#22E3E8;border:1px solid #1B2229;border-radius:999px;padding:3px 10px;white-space:nowrap">✓ You</span></div>
<div style="flex:none;height:300px;background:#000;position:relative"><image-slot id="rr-cmp-current" shape="rect" fit="contain" placeholder="current film"></image-slot><div style="position:absolute;left:31%;top:58%;width:23%;height:19%;border:1.5px solid #FFB020;border-radius:3px;pointer-events:none"><span style="position:absolute;bottom:-22px;left:0;font-family:'IBM Plex Mono',monospace;font-size:11px;color:#FFB020;white-space:nowrap">new since 12 Mar</span></div></div>
<div style="flex:1;overflow:auto;padding:20px 22px">
<div style="font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.14em;color:#96A3B0;margin-bottom:8px">IMPRESSION</div>
<div style="font-size:17px;line-height:30px;font-weight:500">Left lower lobe airspace opacity, consistent with pneumonia in the appropriate clinical setting.</div>
</div>
</div>
</div>
<div style="flex:none;border-top:1px solid #1B2229;padding:22px 30px;display:grid;grid-template-columns:150px 200px 240px 1fr;gap:30px;align-items:start">
<div><div style="font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.14em;color:#96A3B0;margin-bottom:8px">RESOLVED</div><div style="font-size:15px;color:#96A3B0">none</div></div>
<div><div style="font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.14em;color:#96A3B0;margin-bottom:8px">PERSISTENT</div><div style="font-size:15px">Borderline heart size</div></div>
<div><div style="font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.14em;color:#FFB020;margin-bottom:8px">NEW</div><div style="font-size:15px;color:#FFB020">Left lower lobe opacity · Consolidation</div></div>
<div><div style="font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.14em;color:#96A3B0;margin-bottom:8px">NARRATIVE · WRITTEN BY THE MODEL FROM THE SPLIT AT LEFT</div><div style="font-size:14.5px;line-height:1.65;color:#8C9AA8">New left lower lobe airspace opacity has appeared in the 141 days since the prior study, on a background of unchanged borderline cardiac size. Nothing present in March has resolved.</div></div>
</div>
</div>
</sc-if>

<sc-if value="{{ isSettings }}" hint-placeholder-val="{{ false }}">
<div style="flex:none;height:60px;border-bottom:1px solid #1B2229;display:flex;align-items:center;padding:0 30px;gap:14px">
<h1 style="font-size:16px;font-weight:600;margin:0">Settings</h1>
<span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#96A3B0;white-space:nowrap">s.rahman@radassist.local</span>
<span style="flex:1"></span>
<span style="font-size:14px;color:#22E3E8">All changes saved</span>
<button type="button" onClick="{{ goLogout }}" style="font-family:'Space Grotesk';font-size:14px;color:#E6EDF3;background:transparent;border:1px solid #2A343D;border-radius:7px;padding:7px 15px;cursor:pointer;white-space:nowrap" style-hover="border-color:#FFB020;color:#FFB020">Sign out</button>
</div>
<div style="flex:1;overflow:auto;padding:34px 30px">
<div style="max-width:1080px;display:grid;grid-template-columns:1fr 1fr;gap:44px;align-items:start">

<div>
<h3 style="font-size:22px;letter-spacing:-.02em;font-weight:600;margin:0 0 6px">Identity and signature</h3>
<p style="font-size:14px;color:#8C9AA8;margin:0 0 22px">Printed at the foot of every report you sign.</p>
<div style="display:flex;flex-direction:column;gap:16px">
<div style="display:flex;align-items:center;gap:18px">
<span style="width:76px;height:76px;flex:none;border-radius:50%;overflow:hidden;background:#1B2229;display:block"><image-slot id="rr-avatar" shape="circle" fit="cover" placeholder="profile photo"></image-slot></span>
<div style="display:flex;flex-direction:column;gap:7px">
<span style="font-size:13px;color:#8C9AA8">Profile photo</span>
<div style="display:flex;gap:9px">
<span style="font-size:13.5px;border:1px solid #2A343D;border-radius:7px;padding:8px 14px;color:#E6EDF3;white-space:nowrap">Change photo</span>
<span style="font-size:13.5px;border:1px solid transparent;border-radius:7px;padding:8px 10px;color:#96A3B0;white-space:nowrap">Remove</span>
</div>
<span style="font-size:12.5px;color:#96A3B0">Shown to you only. Not printed on reports.</span>
</div>
</div>
<label style="display:flex;flex-direction:column;gap:7px"><span style="font-size:13px;color:#8C9AA8">Full name</span><span style="height:46px;border:1px solid #2A343D;border-radius:8px;display:flex;align-items:center;padding:0 14px;font-size:15px;background:#0E1318;white-space:nowrap">Dr. Sumaiya Rahman</span></label>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
<label style="display:flex;flex-direction:column;gap:7px"><span style="font-size:13px;color:#8C9AA8">Qualifications</span><span style="height:46px;border:1px solid #2A343D;border-radius:8px;display:flex;align-items:center;padding:0 14px;font-size:14px;background:#0E1318;white-space:nowrap">MBBS, FCPS (Radiology)</span></label>
<label style="display:flex;flex-direction:column;gap:7px"><span style="font-size:13px;color:#8C9AA8">BMDC number</span><span style="height:46px;border:1px solid #2A343D;border-radius:8px;display:flex;align-items:center;padding:0 14px;font-family:'IBM Plex Mono',monospace;font-size:15px;background:#0E1318;white-space:nowrap">A-41822</span></label>
</div>
<p style="font-size:13.5px;line-height:1.6;color:#96A3B0;margin:0">Recorded as entered. This system has no access to the BMDC registry and cannot verify it.</p>
<div style="border:1px solid #1B2229;border-radius:10px;background:#0E1318;padding:20px;white-space:nowrap">
<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;color:#96A3B0;margin-bottom:14px">AS IT APPEARS ON A SIGNED REPORT</div>
<div style="border-top:2px solid #22E3E8;padding-top:12px"><div style="font-size:16px;font-weight:500">Dr. Sumaiya Rahman</div><div style="font-size:14px;color:#8C9AA8;margin-top:2px">MBBS, FCPS (Radiology)</div><div style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#96A3B0;margin-top:6px;white-space:nowrap">BMDC A-41822 · signed 31 Jul 2026</div></div>
</div>
</div>
</div>

<div style="display:flex;flex-direction:column;gap:36px">
<div>
<h3 style="font-size:22px;letter-spacing:-.02em;font-weight:600;margin:0 0 6px">Reading defaults</h3>
<p style="font-size:14px;color:#8C9AA8;margin:0 0 22px">Applied to every new examination you start.</p>
<div style="display:flex;flex-direction:column;gap:22px">
<div><div style="font-size:14px;color:#8C9AA8;margin-bottom:10px">Retrieval depth</div><div style="display:flex;gap:9px"><span style="border:1px solid #2A343D;border-radius:999px;padding:9px 20px;font-size:14px;color:#8C9AA8;white-space:nowrap">Top 3</span><span style="border:1px solid #22E3E8;background:rgba(34,227,232,.12);color:#22E3E8;border-radius:999px;padding:9px 20px;font-size:14px;white-space:nowrap">Top 5</span><span style="border:1px solid #2A343D;border-radius:999px;padding:9px 20px;font-size:14px;color:#8C9AA8;white-space:nowrap">Top 10</span></div><p style="font-size:13px;color:#96A3B0;margin:9px 0 0">Five is what the evaluation used. More cases means slower generation.</p></div>
<div><div style="font-size:14px;color:#8C9AA8;margin-bottom:10px">Report language</div><div style="display:flex;gap:9px"><span style="border:1px solid #22E3E8;background:rgba(34,227,232,.12);color:#22E3E8;border-radius:999px;padding:9px 20px;font-size:14px;white-space:nowrap">English</span><span style="border:1px solid #2A343D;border-radius:999px;padding:9px 20px;font-family:'Noto Sans Bengali',sans-serif;font-size:14px;color:#8C9AA8;white-space:nowrap">বাংলা</span></div></div>
<div style="display:flex;align-items:flex-start;gap:14px"><span style="width:38px;height:20px;border-radius:999px;background:#2A343D;position:relative;flex:none;margin-top:3px"><span style="position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:#8C9AA8"></span></span><div><div style="font-size:15px">Skip the questionnaire by default</div><div style="font-size:13.5px;line-height:1.55;color:#96A3B0;margin-top:2px">Off — when retrieval is ambiguous the questions are worth thirty seconds.</div></div></div>
</div>
</div>
<div>
<h3 style="font-size:22px;letter-spacing:-.02em;font-weight:600;margin:0 0 6px">This machine</h3>
<p style="font-size:14px;color:#8C9AA8;margin:0 0 18px">Everything runs locally. Nothing leaves the building.</p>
<div style="border-top:1px solid #1B2229">
<sc-for list="{{ services }}" as="sv" hint-placeholder-count="4">
<div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid #1B2229">
<span style="{{ sv.dot }}"></span>
<span style="font-size:14px;color:#8C9AA8">{{ sv.name }}</span>
<span style="flex:1"></span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:13px;white-space:nowrap">{{ sv.value }}</span>
</div>
</sc-for>
<div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid #1B2229"><span style="font-size:14px;color:#8C9AA8">Archive cases indexed</span><span style="flex:1"></span><span style="font-family:'IBM Plex Mono',monospace;font-size:13px;white-space:nowrap">2,460</span></div>
<div style="display:flex;align-items:center;gap:12px;padding:12px 0"><span style="font-size:14px;color:#8C9AA8">Original images stored</span><span style="flex:1"></span><span style="font-family:'IBM Plex Mono',monospace;font-size:13px;color:#22E3E8;white-space:nowrap">0</span></div>
</div>
<p style="font-size:13.5px;line-height:1.65;color:#96A3B0;margin:16px 0 0">The system cannot disclose unmasked PHI from storage, because unmasked PHI is never stored.</p>
</div>
</div>
</div>
</div>
</sc-if>

</div>
</div>

<div style="width:1440px;margin:16px auto 0;display:flex;gap:26px;align-items:flex-start">
<p style="flex:1;font-size:14px;line-height:1.65;color:#8C9AA8;margin:0"><span style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#96A3B0">Note · </span>{{ note }}</p>
<p style="flex:none;width:300px;font-family:'IBM Plex Mono',monospace;font-size:11px;line-height:1.7;color:#96A3B0;margin:0">Every black film area is a drop slot. Base 15px, one accent, hairlines only — no cards.</p>
</div>

</div>
</x-dc>
<script type="text/x-dc" data-dc-script data-props="{&quot;$preview&quot;:{&quot;width&quot;:1500,&quot;height&quot;:1060}}">
const SCREENS = [
  ['landing','/','Landing'],['login','/login','Sign in'],['register','/register','Register'],
  ['dashboard','/dashboard','Queue'],['search','/patients/search','Find patient'],
  ['newpatient','/patients/new','Register patient'],['patient','/patients/:id','Patient'],
  ['upload','/patients/:id/upload','New examination'],['workspace','/reports/:id','Workspace'],
  ['regen','· regenerate','Workspace'],['diff','· changes','Workspace'],['finalize','· sign','Workspace'],
  ['explain','/reports/:id/explain','Explainability'],['compare','/reports/:id/compare','Compare'],
  ['settings','/settings','Settings']
];

const NOTES = {
  landing:'Dark hero, 62px headline, and the product moment itself: film → drafted impression → the three cases behind it. Numbers are the honest ones, no accuracy claim.',
  login:'The film fills the left half at half opacity; the form is the only lit thing. Service status states when it was checked and that generation will feel slow while Ollama warms.',
  register:'Qualifications and BMDC belong here, not in Settings — they print on every report, so the signature block builds live beside the fields.',
  dashboard:'One sentence instead of a metrics wall: "Three reports are waiting on you." Oldest first, waiting time in words, amber only on the one that is late.',
  search:'One field takes a code or a name. The transliteration reality is stated in prose, not hidden behind a mode toggle.',
  newpatient:'Duplicate detection while you type — a duplicate patient silently breaks the prior-study timeline, the one thing this product cannot recover from.',
  patient:'Prior studies as a filmstrip list with the gap between studies made explicit, and comparison promoted into the header.',
  upload:'PHI reveal is the whole viewport with the handle on the film. The questionnaire appears with its reason attached: top match 71.4% against a usual 84–93%.',
  workspace:'The screen that matters. Film takes the flexible width; the report is a 530px column where every clause carries its case numbers; amber marks the one clause nothing supports.',
  regen:'The candidate opens under the clause it replaces, old text struck through above it. Nothing below moves, and discarding fires no request.',
  diff:'Edit percentage set at 44px because it is the project\u2019s headline metric — struck grey is the model\u2019s words, cyan underline is yours.',
  finalize:'The one modal. Document as it will print, the checks that passed, and what gets recorded — including that the follow-up interval was yours alone.',
  explain:'A query log, not a chat: 22px ruled question, 17px prose answer, cases cited underneath, and the sentence under question pinned on the right.',
  compare:'Prior left, this study right with the new finding boxed in amber. Deterministic split along the bottom, model narrative labelled as narrative.',
  settings:'Three plain-language groups. Every honesty string kept: BMDC cannot be verified, and original images stored is a cyan zero.'
};

const RAIL = [
  ['dashboard','▤','Queue'],['search','⌕','Find patient'],['patient','◫','Patients'],
  ['upload','＋','New examination'],['workspace','▥','Workspace'],
  ['explain','?','Explainability'],['compare','⇄','Compare']
];

const SERVICES = [
  {name:'FastAPI',value:'ok · :8000',state:'ok'},
  {name:'Ollama',value:'llama3:8b · 22s',state:'warn'},
  {name:'ChromaDB',value:'2,460 vectors',state:'ok'},
  {name:'GPU',value:'RTX 3060 · 12 GB',state:'ok'}
];

const QUEUE = [
  {name:'Rafiqul Islam',code:'PAT-000188',study:'ACC-2026-0834',waiting:'2 days',late:true,status:'AI draft',tone:'warn',edited:'0.0%',action:'Review',first:true},
  {name:'Nasrin Akter',code:'PAT-000317',study:'ACC-2026-0871',waiting:'25 min',late:false,status:'Edited by you',tone:'cyan',edited:'18.4%',action:'Resume'},
  {name:'Md. Shahidul Haque',code:'PAT-000102',study:'ACC-2026-0869',waiting:'1 hour',late:false,status:'Under review',tone:'cyan',edited:'6.2%',action:'Resume'},
  {name:'Ayesha Siddika',code:'PAT-000204',study:'ACC-2026-0866',waiting:'signed 08:41',late:false,status:'Signed',tone:'muted',edited:'21.7%',action:'Open'}
];

const MATCHES = [
  {name:'Md. Shahidul Haque',alias:'also spelled Shohidul Hoque',code:'PAT-000102',dob:'19 Jul 1968',last:'Mild cardiomegaly. Clinical correlation advised.',lastDate:'31 Jul 2026 · Dr. Haque'},
  {name:'Shahidul Huq',alias:'no alternate spellings recorded',code:'PAT-000239',dob:'02 Mar 1981',last:'No acute cardiopulmonary abnormality.',lastDate:'18 Jun 2026 · Dr. Rahman'},
  {name:'Md. Shahid Hoque',alias:'possible transliteration match',code:'PAT-000291',dob:'11 Nov 1975',last:'Right upper zone fibrotic change.',lastDate:'02 May 2026 · Dr. Rahman'}
];

const PRIORS = [
  {slotId:'rr-prior-3',date:'31 Jul 2026',projection:'PA',acc:'ACC-2026-0871',status:'Edited by you',tone:'cyan',owner:'✓ You',mine:true,impression:'Left lower lobe airspace opacity, consistent with pneumonia in the appropriate clinical setting.',gap:'141 days after prior',compare:false,current:true},
  {slotId:'rr-prior-2',date:'12 Mar 2026',projection:'PA',acc:'ACC-2026-0442',status:'Signed',tone:'muted',owner:'✓ You',mine:true,impression:'No acute cardiopulmonary abnormality.',gap:'128 days after prior',compare:true,current:false},
  {slotId:'rr-prior-1',date:'04 Nov 2025',projection:'PA · lateral',acc:'ACC-2025-1187',status:'Signed',tone:'muted',owner:'Dr. Haque',mine:false,impression:'Mild cardiomegaly. Lungs clear. No pleural effusion.',gap:'first study on record',compare:true,current:false}
];

const STEPS = [
  {label:'Upload',time:'0.6s',done:true},
  {label:'PHI masking · 2 regions',time:'1.1s',done:true},
  {label:'BiomedCLIP embedding',time:'0.3s',done:true},
  {label:'ChromaDB retrieval · 5 of 2,460',time:'0.4s',done:true},
  {label:'Llama 3 8B drafting · section 4 of 7',time:'12.4s',done:false}
];

const CASES = [
  {sup:'01',num:'91.2',id:'CXR-2117',impression:'Left lower lobe pneumonia. Heart size normal, no effusion.',cites:'cited in 2 sentences',lit:true},
  {sup:'02',num:'87.4',id:'CXR-0884',impression:'Left basal airspace disease, likely infective.',cites:'cited in 2 sentences',lit:true},
  {sup:'03',num:'84.1',id:'CXR-3390',impression:'Left basal atelectasis with mild volume loss.',cites:'cited in 1 sentence',lit:false}
];

const CLAUSES_EN = [
  {text:'The heart size and mediastinal contours are within normal limits.',sup:'01'},
  {text:'There is ill-defined airspace opacity in the left lower lobe, with air bronchograms.',sup:'01,02'},
  {text:'No pleural effusion or pneumothorax is identified.',sup:'03'},
  {text:'Mild degenerative change of the thoracic spine.',sup:'—',none:true}
];
const CLAUSES_BN = [
  {text:'হৃৎপিণ্ডের আকার এবং মিডিয়াস্টিনামের গঠন স্বাভাবিক সীমার মধ্যে রয়েছে।',sup:'01'},
  {text:'বাম ফুসফুসের নিম্নাংশে অস্বচ্ছতা দেখা যাচ্ছে, সঙ্গে এয়ার ব্রঙ্কোগ্রাম রয়েছে।',sup:'01,02'},
  {text:'কোনো প্লুরাল ইফিউশন বা নিউমোথোরাক্স পাওয়া যায়নি।',sup:'03'},
  {text:'দৃশ্যমান অস্থিসমূহে মৃদু ডিজেনারেটিভ পরিবর্তন রয়েছে।',sup:'—',none:true}
];

const ALT = [
  {label:'Opacity',count:'5 of 5',lit:true},
  {label:'Consolidation',count:'3 of 5',lit:true},
  {label:'Pneumonia',count:'2 of 5',lit:true},
  {label:'Atelectasis',count:'1 of 5',lit:false},
  {label:'Pleural Effusion',count:'0 of 5',lit:false}
];

class Component extends DCLogic {
  state = { screen: 'workspace', tab: 'evidence', lang: 'en' };

  pill(tone) {
    if (tone === 'cyan') return 'display:inline-flex;align-items:center;border:1px solid rgba(34,227,232,.45);background:rgba(34,227,232,.12);color:#22E3E8;border-radius:999px;padding:3px 11px;font-size:12.5px;white-space:nowrap';
    if (tone === 'warn') return 'display:inline-flex;align-items:center;border:1px solid rgba(255,176,32,.5);background:rgba(255,176,32,.1);color:#FFB020;border-radius:999px;padding:3px 11px;font-size:12.5px;white-space:nowrap';
    return 'display:inline-flex;align-items:center;border:1px solid #2A343D;color:#8C9AA8;border-radius:999px;padding:3px 11px;font-size:12.5px;white-space:nowrap';
  }

  renderVals() {
    const s = this.state.screen;
    const bn = this.state.lang === 'bn';
    const isWorkspace = s === 'workspace' || s === 'regen' || s === 'diff' || s === 'finalize';
    const showRail = s !== 'landing' && s !== 'login' && s !== 'register';
    const railWide = showRail;
    const fam = bn ? "'Noto Sans Bengali',sans-serif" : "'Space Grotesk',sans-serif";
    const lh = bn ? '34px' : '29px';
    const go = (k) => () => this.setState({ screen: k });

    const railBtn = (active) =>
      'display:flex;align-items:center;gap:12px;width:100%;border:none;cursor:pointer;text-align:left;border-radius:6px;padding:' +
      (railWide ? '10px 12px' : '10px 0') + ';justify-content:' + (railWide ? 'flex-start' : 'center') +
      ';background:' + (active ? 'rgba(34,227,232,.12)' : 'transparent') + ';color:' + (active ? '#22E3E8' : '#8C9AA8') +
      ";font-family:'Space Grotesk';font-size:14.5px;font-weight:" + (active ? '500' : '400');

    return {
      screens: SCREENS.map(([k, route]) => ({
        route, onClick: go(k),
        btnStyle: "font-family:'IBM Plex Mono',monospace;font-size:10.5px;padding:6px 10px;cursor:pointer;white-space:nowrap;border-radius:6px;border:1px solid " +
          (s === k ? '#22E3E8;background:#22E3E8;color:#04181A' : '#2A343D;background:#0E1318;color:#8C9AA8')
      })),
      screenLabel: (SCREENS.find(x => x[0] === s) || [,, s])[2],
      note: NOTES[s],

      showRail, railWide,
      railHeaderStyle: 'flex:none;height:60px;display:flex;align-items:center;gap:11px;padding:0 ' + (railWide ? '12px 0 18px' : '0') + ';justify-content:' + (railWide ? 'flex-start' : 'center') + ';border-bottom:1px solid #1B2229',
      railStyle: 'width:' + (railWide ? '224px' : '64px') +
        ';flex:none;border-right:1px solid #1B2229;display:flex;flex-direction:column;min-height:0',
      railItems: RAIL.map(([k, glyph, label]) => {
        const active = k === s || (k === 'workspace' && isWorkspace);
        return {
          glyph, label, onClick: go(k), style: railBtn(active),
          glyphStyle: "font-family:'IBM Plex Mono',monospace;font-size:14px;width:18px;flex:none;text-align:center",
          labelStyle: railWide ? 'flex:1;min-width:0;white-space:nowrap' : 'display:none'
        };
      }),
      goSettings: go('settings'),
      goLogout: go('login'),
      signOutStyle: railBtn(false) + ';color:#96A3B0',
      settingsStyle: railBtn(s === 'settings'),
      settingsGlyphStyle: "font-family:'IBM Plex Mono',monospace;font-size:14px;width:18px;flex:none;text-align:center",
      settingsLabelStyle: railWide ? '' : 'display:none',

      isLanding: s === 'landing', isLogin: s === 'login', isRegister: s === 'register',
      isDashboard: s === 'dashboard', isSearch: s === 'search', isNewPatient: s === 'newpatient',
      isPatient: s === 'patient', isUpload: s === 'upload', isExplain: s === 'explain',
      isCompare: s === 'compare', isSettings: s === 'settings',
      isWorkspace, isRegen: s === 'regen', showDiffPanel: s === 'diff', isFinalize: s === 'finalize',

      services: SERVICES.map(v => ({
        name: v.name, value: v.value,
        dot: 'width:8px;height:8px;border-radius:50%;flex:none;background:' + (v.state === 'ok' ? '#22E3E8' : '#FFB020'),
        pill: 'display:inline-flex;align-items:center;gap:8px;border:1px solid #1B2229;border-radius:999px;padding:6px 13px;font-size:12.5px;color:#8C9AA8;white-space:nowrap'
      })),

      queue: QUEUE.map((q, i) => ({
        name: q.name, code: q.code, study: q.study, waiting: q.waiting, status: q.status, edited: q.edited, action: q.action,
        waitColor: q.late ? '#FFB020' : '#8C9AA8',
        chipStyle: this.pill(q.tone),
        rowStyle: 'display:grid;grid-template-columns:1.5fr 150px 130px 150px 100px 120px;gap:14px;align-items:center;padding:18px 4px;border-bottom:1px solid #1B2229',
        actionStyle: 'font-size:14px;border-radius:6px;padding:8px 15px;white-space:nowrap;' +
          (q.first ? 'font-weight:600;background:#22E3E8;color:#04181A' : 'border:1px solid #2A343D;color:#8C9AA8')
      })),

      matches: MATCHES,

      priors: PRIORS.map((p, i) => ({
        slotId: p.slotId, date: p.date, projection: p.projection, acc: p.acc, status: p.status,
        owner: p.owner, impression: p.impression, gap: p.gap,
        chipStyle: this.pill(p.tone),
        ownerStyle: p.mine ? this.pill('cyan') : this.pill('muted'),
        compareStyle: p.compare ? 'font-size:13.5px;color:#22E3E8' : 'display:none',
        rowStyle: 'display:flex;gap:18px;padding:22px 4px;border-bottom:1px solid #1B2229' +
          (p.current ? ';background:rgba(34,227,232,.03)' : '')
      })),

      steps: STEPS.map(k => ({
        label: k.label, time: k.done ? k.time : k.time + '…',
        icon: k.done ? '✓' : '◐',
        iconStyle: "font-family:'IBM Plex Mono',monospace;font-size:13px;width:16px;flex:none;color:" + (k.done ? '#22E3E8' : '#FFB020'),
        textColor: k.done ? '#8C9AA8' : '#E6EDF3'
      })),

      cases: CASES.map(c => ({
        sup: c.sup, num: c.num, id: c.id, impression: c.impression, cites: c.cites,
        slotId: 'rr-case-' + c.id.toLowerCase(),
        numStyle: "font-family:'IBM Plex Mono',monospace;font-size:26px;font-weight:500;letter-spacing:-.03em;color:" + (c.lit ? '#E6EDF3' : '#8C9AA8')
      })),

      railTabs: ['evidence', 'agreement', 'alternatives'].map(t => ({
        label: t.charAt(0).toUpperCase() + t.slice(1),
        onClick: () => this.setState({ tab: t }),
        style: "flex:1;border:none;cursor:pointer;background:transparent;padding:14px 4px;font-family:'Space Grotesk';font-size:13.5px;font-weight:500;border-bottom:2px solid " +
          (this.state.tab === t ? '#22E3E8;color:#22E3E8' : 'transparent;color:#96A3B0')
      })),
      tabEvidence: this.state.tab === 'evidence',
      tabAgreement: this.state.tab === 'agreement',
      tabAlternatives: this.state.tab === 'alternatives',
      altLabels: ALT.map(a => ({ label: a.label, count: a.count, color: a.lit ? '#E6EDF3' : '#8C9AA8' })),

      clauses: (bn ? CLAUSES_BN : CLAUSES_EN).map(c => ({
        text: c.text, sup: c.sup,
        supStyle: "font-family:'IBM Plex Mono',monospace;font-size:11px;flex:none;width:38px;padding-top:8px;color:" + (c.none ? '#FFB020' : '#22E3E8'),
        textStyle: 'flex:1;font-family:' + fam + ';font-size:17px;line-height:' + lh + ';max-width:' + (bn ? '40ch' : '52ch') + (c.none ? ';color:#8C9AA8' : ''),
        tag: c.none ? '  NO CASE' : '',
        tagStyle: c.none ? "font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.08em;color:#FFB020;white-space:nowrap" : 'display:none'
      })),

      diffToggleStyle: 'font-size:13.5px;cursor:pointer;border-bottom:1px solid ' +
        (s === 'diff' ? '#22E3E8;color:#22E3E8' : '#2A343D;color:#8C9AA8'),
      statusLabel: s === 'diff' ? 'Edited by you' : 'Unsigned draft',
      statusStyle: this.pill(s === 'diff' ? 'cyan' : 'warn'),
      enTab: "font-family:'IBM Plex Mono',monospace;font-size:11px;padding:6px 11px;cursor:pointer;" +
        (bn ? 'color:#8C9AA8' : 'background:#1B2229;color:#E6EDF3'),
      bnTab: "font-family:'Noto Sans Bengali',sans-serif;font-size:11.5px;padding:6px 11px;cursor:pointer;" +
        (bn ? 'background:#1B2229;color:#E6EDF3' : 'color:#8C9AA8'),
      reportKicker: s === 'finalize' ? 'REPORT · READY TO SIGN'
        : (bn ? 'খসড়া · ৩টি কেস · 12.4s' : 'DRAFT · FROM 3 CASES · 12.4s'),

      txImpression: bn
        ? 'বাম ফুসফুসের নিম্নাংশের অস্বচ্ছতা, সম্ভবত নিউমোনিয়া। ক্লিনিক্যাল সহসম্পর্ক প্রয়োজন।'
        : 'Left lower lobe airspace opacity, consistent with pneumonia in the appropriate clinical setting.',
      impressionStyle: 'flex:1;font-family:' + fam + ';font-size:21px;line-height:' + (bn ? '38px' : '34px') + ';font-weight:500;letter-spacing:-.01em;max-width:' + (bn ? '38ch' : '46ch'),
      txRec: bn
        ? 'উপসর্গ থাকলে ৪–৬ সপ্তাহ পরে পুনরায় এক্স-রে করুন।'
        : 'Follow-up radiograph in 4–6 weeks if symptoms persist.',
      recStyle: 'flex:1;font-family:' + fam + ';font-size:17px;line-height:' + lh + ';max-width:' + (bn ? '40ch' : '52ch')
    };
  }
}
</script>
</body>
</html>
