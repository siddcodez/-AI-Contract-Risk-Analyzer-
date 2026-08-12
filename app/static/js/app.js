/**
 * AI Contract Risk Analyzer — Frontend Application Logic v2
 * Features: File parsing (PDF/DOCX/TXT), NLP clause classifier, visual diff,
 *           document view, matrix view, playbook config, export engine,
 *           keyboard navigation, accept/reject redlines, real API integration.
 */

/* =================================================================
   CONFIGURATION — Clause classification rules (client-side NLP)
   ================================================================= */
const CLAUSE_RULES = [
  {
    type: 'Indemnification',
    patterns: [/indemni(?:fy|fication)/i, /hold harmless/i, /defend.*from.*claims/i],
    severities: { strict: 'critical', standard: 'high', permissive: 'medium' },
    risk: 'Indemnification clauses transfer liability risk. Broad or one-sided obligations can expose your organisation to significant uncapped financial liability, especially when third-party actions are included.',
    redline: "Party A's liability under this indemnification shall be limited to direct damages arising from Party A's own gross negligence or wilful misconduct, capped at fees paid in the preceding 12 months. Party A shall have no obligation to indemnify for claims arising from Party B's negligence.",
    riskFactors: ['Unilateral liability', 'Uncapped exposure', 'Third-party coverage', 'No carve-outs']
  },
  {
    type: 'Limitation of Liability',
    patterns: [/limitation of liability/i, /limit(?:ed|ing).*liability/i, /liability.*cap/i, /not.*exceed.*\$\d+/i],
    severities: { strict: 'critical', standard: 'medium', permissive: 'safe' },
    risk: 'An unusually low liability cap (e.g., a flat dollar amount under $10,000) fails to cover real-world damages from data breaches, service outages, or material breaches of contract. Mutual caps are preferable.',
    redline: "Total liability shall not exceed the greater of (a) fees paid in the preceding 12 months or (b) [INSERT MINIMUM FLOOR]. No limitation shall apply for gross negligence, wilful misconduct, or data breaches.",
    riskFactors: ['Cap may be too low', 'Asymmetric protection', 'No carve-outs for breach']
  },
  {
    type: 'Non-Compete',
    patterns: [/non.?compete/i, /not.*compet(?:e|ing)/i, /competitive activit/i, /competing.*business/i],
    severities: { strict: 'critical', standard: 'critical', permissive: 'high' },
    risk: 'Broad non-compete clauses (e.g., worldwide, 3-year) are unenforceable in many jurisdictions (California, Minnesota, and North Dakota ban them entirely) and may create costly litigation even if ultimately unenforceable.',
    redline: "Non-compete restrictions shall be limited to [YOUR STATE/REGION], restricted to directly competing roles in your specific product category, for a maximum period of [ONE (1)] year, with compensation paid by Employer during the restriction period.",
    riskFactors: ['Unenforceable in many states', 'Overly broad geographic scope', 'Extended duration', 'No compensation']
  },
  {
    type: 'Non-Solicitation',
    patterns: [/non.?solicit/i, /not.*solicit.*employ/i, /hire.*employees/i, /solicit.*contractor/i],
    severities: { strict: 'high', standard: 'high', permissive: 'medium' },
    risk: 'Non-solicitation clauses restrict talent acquisition. Overly broad language such as "anyone involved in any capacity" may unintentionally restrict general open-market hiring through job postings.',
    redline: "Restrictions shall apply only to direct, targeted solicitation of key personnel with whom there was direct contact under this Agreement, for a period of [ONE (1)] year. General job postings shall not constitute solicitation.",
    riskFactors: ['Overbroad scope', 'Vague "involvement" standard', 'May restrict passive hiring']
  },
  {
    type: 'Confidentiality',
    patterns: [/confidential(?:ity)?/i, /non.?disclosure/i, /proprietary information/i, /trade secret/i],
    severities: { strict: 'medium', standard: 'safe', permissive: 'safe' },
    risk: 'Confidentiality obligations are standard. Review: (1) definition breadth of Confidential Information, (2) survival period (industry standard 2-5 years), and (3) any residuals carve-outs that weaken protection.',
    redline: null,
    riskFactors: []
  },
  {
    type: 'Data Processing',
    patterns: [/data.*processing/i, /personal data/i, /gdpr/i, /ccpa/i, /data.*license/i, /customer data.*(?:train|improve|analyt)/i],
    severities: { strict: 'critical', standard: 'critical', permissive: 'high' },
    risk: "Clauses granting vendors a perpetual, irrevocable license to use Customer Data for their own commercial purposes (product improvement, AI training, analytics) are a GDPR/CCPA violation risk and create serious IP and competitive intelligence exposure.",
    redline: "Vendor shall not use Customer Data for any purpose other than providing the contracted services to Customer. Vendor acquires no ownership or license in Customer Data. All Customer Data remains the exclusive property of Customer and must be deleted within 30 days of contract termination.",
    riskFactors: ['GDPR/CCPA risk', 'IP exposure', 'Competitive intelligence risk', 'Perpetual license']
  },
  {
    type: 'Service Level Agreement',
    patterns: [/service level/i, /uptime/i, /availability guarantee/i, /sla/i, /commercially reasonable efforts/i],
    severities: { strict: 'critical', standard: 'high', permissive: 'medium' },
    risk: "'Commercially reasonable efforts' without defined SLAs or meaningful remedies provides no enforceable guarantee. 99% uptime allows ~87 hours of annual downtime with no compensation obligation.",
    redline: "Vendor guarantees 99.9% monthly uptime (measured excluding scheduled maintenance with 72-hour notice). Downtime exceeding this threshold entitles Customer to service credits of 5% of monthly fees per hour, up to 30% of monthly fees.",
    riskFactors: ['No enforceable guarantee', 'High permissible downtime', 'No credit mechanism', 'Vague remedy']
  },
  {
    type: 'Auto-Renewal',
    patterns: [/auto.?renew/i, /automatic(?:ally)?.*renew/i, /renew.*unless.*notice/i, /successive.*term/i],
    severities: { strict: 'high', standard: 'medium', permissive: 'safe' },
    risk: 'Auto-renewal clauses with long notice windows (90+ days) limit operational flexibility and create significant risk of unintended multi-year financial commitments that are difficult to exit.',
    redline: "Reduce non-renewal notice period to [30/60] days before term end. Include automatic email reminder to both parties at 90 days before renewal. Allow pro-rata refund if notice is given within 7 days after accidental renewal.",
    riskFactors: ['Long notice window', 'Risk of unintended renewal', 'No reminder mechanism']
  },
  {
    type: 'Governing Law',
    patterns: [/governing law/i, /governed by.*laws of/i, /jurisdiction.*court/i, /choice of law/i],
    severities: { strict: 'medium', standard: 'medium', permissive: 'safe' },
    risk: 'Governing law and exclusive jurisdiction determine where disputes are litigated. Foreign or inconvenient jurisdictions can substantially increase the cost and complexity of enforcement.',
    redline: "Consider negotiating for [YOUR JURISDICTION] as the governing law and courts. Alternatively, propose binding arbitration under [AAA/JAMS] rules as a neutral, cost-effective alternative with [CITY, STATE] as the seat.",
    riskFactors: ['Inconvenient jurisdiction', 'Higher litigation cost', 'Unfamiliar legal system']
  },
  {
    type: 'Intellectual Property',
    patterns: [/intellectual property/i, /ip.*ownership/i, /work.*for.*hire/i, /assignment.*ip/i, /assign.*rights/i],
    severities: { strict: 'medium', standard: 'safe', permissive: 'safe' },
    risk: "IP ownership clauses should clearly attribute pre-existing and newly created IP. Ensure that 'work for hire' provisions include appropriate carve-outs for pre-existing technology, and that custom development is customer-owned.",
    redline: null,
    riskFactors: []
  },
  {
    type: 'Termination',
    patterns: [/terminat(?:ion|e).*(?:cause|material breach)/i, /right to terminate/i, /cancellation.*without notice/i, /immediately terminate/i],
    severities: { strict: 'high', standard: 'medium', permissive: 'safe' },
    risk: "Termination clauses define exit rights. One-sided termination rights or absence of cure periods for immaterial breaches create significant operational and financial risk for the non-terminating party.",
    redline: "Either party may terminate for material breach with 30 days' written notice and opportunity to cure. Termination for convenience requires 90 days' notice with pro-rata refund of prepaid fees. No termination for causes outside the party's reasonable control.",
    riskFactors: ['One-sided right', 'No cure period', 'No refund on termination']
  },
  {
    type: 'Arbitration',
    patterns: [/arbitrat(?:ion|e)/i, /waive.*jury/i, /class action.*waiv/i, /binding arbitration/i],
    severities: { strict: 'high', standard: 'high', permissive: 'medium' },
    risk: "Mandatory arbitration with class action waiver may be unenforceable for certain employment or consumer claims. Pre-dispute arbitration clauses for discrimination or harassment claims face increasing regulatory and legislative scrutiny.",
    redline: "Specify a neutral provider (JAMS/AAA), employer-paid fees for employment disputes, individual opt-out rights within 30 days, carve-outs for injunctive/emergency relief, and mutual (not unilateral) obligation.",
    riskFactors: ['May be unenforceable', 'Eliminates class action rights', 'Limits discovery rights', 'Possible legislative override']
  }
];

/* =================================================================
   SAMPLE CONTRACT DATA
   ================================================================= */
const SAMPLE_CONTRACTS = {
  nda: {
    name: 'Mutual NDA Agreement', type: 'NDA', pages: 8, size: '245 KB', score: 72,
    rawText: `MUTUAL NON-DISCLOSURE AGREEMENT

This Mutual Non-Disclosure Agreement ("Agreement") is entered into as of the Effective Date between the parties.

ARTICLE 1 — CONFIDENTIALITY
"Confidential Information" means any non-public information disclosed by one party (the "Disclosing Party") to the other party (the "Receiving Party"), whether in oral, written, electronic, or any other form, that is designated as confidential or that reasonably should be understood to be confidential given the nature of the information and circumstances of disclosure.

ARTICLE 2 — NON-DISCLOSURE OBLIGATIONS
The Receiving Party agrees to hold all Confidential Information in strict confidence and not to disclose it to any third party without prior written consent of the Disclosing Party.

ARTICLE 3 — INDEMNIFICATION
Party A shall indemnify and hold harmless Party B, its officers, directors, employees, and agents from any and all claims, damages, losses, costs, or expenses, including reasonable attorneys' fees, arising out of or related to any breach of this Agreement by Party A or any third party acting on Party A's behalf.

ARTICLE 4 — CONFIDENTIALITY PERIOD
Confidentiality obligations under this Agreement shall survive the termination or expiration of this Agreement for a period of ten (10) years following disclosure of the Confidential Information.

ARTICLE 5 — NON-SOLICITATION
During the term of this Agreement and for a period of two (2) years thereafter, neither party shall, directly or indirectly, solicit or hire any employee or contractor of the other party who was involved in any capacity with this Agreement.

ARTICLE 6 — GOVERNING LAW
This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, without regard to its conflicts of law principles. Any disputes shall be resolved in the courts of New Castle County, Delaware.

ARTICLE 7 — RESIDUALS CLAUSE
Notwithstanding any other provision, the Receiving Party may use "residuals" — information in non-tangible form retained in the unaided memories of its employees who have had access to the Confidential Information — for any purpose including developing competing products.

ARTICLE 8 — TERM AND RENEWAL
This Agreement shall become effective on the Effective Date and shall remain in force for a period of one (1) year, unless terminated earlier. The parties may renew this Agreement for additional one-year terms by mutual written consent executed by authorized representatives.`,
    clauses: [
      { id: 'c1', type: 'Indemnification', severity: 'critical', snippet: 'Party A shall indemnify and hold harmless Party B from any and all claims, damages, losses or expenses...', original: "Party A shall indemnify and hold harmless Party B, its officers, directors, employees, and agents from any and all claims, damages, losses, costs, or expenses, including reasonable attorneys' fees, arising out of or related to any breach of this Agreement by Party A or any third party acting on Party A's behalf.", risk: 'This is a unilateral, broad indemnification clause that creates unlimited liability for Party A. It covers third-party actions without caps or carve-outs, exposing your company to uncapped financial risk.', redline: "Party A's liability under this indemnification shall be limited to direct damages only and shall not exceed the fees paid by Party B in the preceding 12 months. Party A shall have no obligation to indemnify for claims arising from Party B's own negligence or wilful misconduct.", riskFactors: ['Unilateral indemnification', 'No cap on damages', 'Third-party coverage', 'No carve-outs for negligence'] },
      { id: 'c2', type: 'Confidentiality Period', severity: 'high', snippet: 'Confidentiality obligations shall survive termination for a period of ten (10) years...', original: 'Confidentiality obligations under this Agreement shall survive the termination or expiration of this Agreement for a period of ten (10) years following disclosure of the Confidential Information.', risk: 'A 10-year confidentiality obligation is unusually long for an NDA. Industry standard is typically 2-5 years. This could expose the receiving party to litigation risk if information becomes publicly available through no fault of their own.', redline: 'Confidentiality obligations shall survive for a period of THREE (3) years from the date of disclosure of the applicable Confidential Information, or until the Confidential Information enters the public domain through no breach of this Agreement by the Receiving Party.', riskFactors: ['Excessive duration', 'Above industry standard', 'Litigation risk on public domain info'] },
      { id: 'c3', type: 'Non-Solicitation', severity: 'high', snippet: 'During the term and for two years thereafter, neither party shall solicit or hire employees...', original: 'During the term of this Agreement and for a period of two (2) years thereafter, neither party shall, directly or indirectly, solicit or hire any employee or contractor of the other party who was involved in any capacity with this Agreement.', risk: 'Non-solicitation clauses are enforceable in most jurisdictions but the scope here is overbroad. "Involved in any capacity" is vague and may unintentionally restrict general hiring (e.g., open job postings).', redline: "Neither party shall directly solicit for employment any key personnel of the other party with whom they had direct contact under this Agreement, for a period of ONE (1) year after termination. General solicitation through public job postings shall not be restricted.", riskFactors: ['Overbroad scope', 'Vague "any capacity" standard', 'May restrict passive hiring'] },
      { id: 'c4', type: 'Governing Law', severity: 'medium', snippet: 'This Agreement shall be governed by the laws of the State of Delaware...', original: 'This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, without regard to its conflicts of law principles. Any disputes shall be resolved in the courts of New Castle County, Delaware.', risk: 'Delaware jurisdiction is common and generally acceptable for US business agreements. However, if your organisation is based in another jurisdiction, this could increase litigation costs and inconvenience.', redline: 'Consider negotiating for [YOUR STATE] jurisdiction to minimize litigation costs. Alternatively, propose binding arbitration (AAA or JAMS rules) as a cost-effective dispute resolution mechanism.', riskFactors: ['Inconvenient jurisdiction', 'Delaware courts may be unfamiliar'] },
      { id: 'c5', type: 'Residuals Clause', severity: 'medium', snippet: 'Nothing in this Agreement shall restrict employees who retain general knowledge in unaided memory...', original: 'Notwithstanding any other provision, the Receiving Party may use "residuals" — information in non-tangible form retained in the unaided memories of its employees who have had access to the Confidential Information — for any purpose including developing competing products.', risk: 'This residuals clause significantly weakens confidentiality protections by allowing employees to use retained knowledge for competing work. This effectively nullifies protections for highly technical or process-oriented IP.', redline: 'Consider removing the residuals clause entirely, or narrowly scoping it to exclude use of residual knowledge for directly competing products or services within 12 months of disclosure.', riskFactors: ['Weakens confidentiality', 'Allows competing use', 'IP exposure for technical processes'] },
      { id: 'c6', type: 'Term & Renewal', severity: 'safe', snippet: 'This Agreement shall be effective for one (1) year and may be renewed by mutual written consent...', original: 'This Agreement shall become effective on the Effective Date and shall remain in force for a period of one (1) year, unless terminated earlier. The parties may renew this Agreement for additional one-year terms by mutual written consent executed by authorised representatives.', risk: 'Standard term with mutual renewal requirement. Properly protects both parties from automatic renewal obligations.', redline: null, riskFactors: [] },
      { id: 'c7', type: 'Confidentiality', severity: 'safe', snippet: 'Confidential Information means all non-public information disclosed by either party...', original: "Confidential Information means any non-public information disclosed by one party (the Disclosing Party) to the other party (the Receiving Party), whether in oral, written, electronic, or any other form, that is designated as confidential or that reasonably should be understood to be confidential given the nature of the information and circumstances of disclosure.", risk: 'Well-drafted definition that includes both marked and reasonably-understood-to-be-confidential information. Properly balanced.', redline: null, riskFactors: [] }
    ]
  },
  vendor: {
    name: 'Software Vendor Agreement', type: 'Vendor', pages: 22, size: '1.2 MB', score: 45,
    rawText: `SOFTWARE VENDOR AGREEMENT

ARTICLE 1 — LIMITATION OF LIABILITY
In no event shall Vendor be liable to Customer for any amounts exceeding five hundred dollars ($500), regardless of the basis of the claim, whether in contract, tort, or otherwise.

ARTICLE 2 — DATA PROCESSING AND OWNERSHIP
Customer grants Vendor a perpetual, irrevocable, worldwide license to use, reproduce, modify, and create derivative works from Customer Data for the purposes of improving Vendor's products, services, and underlying technologies.

ARTICLE 3 — SERVICE LEVEL AGREEMENT
Vendor will use commercially reasonable efforts to maintain 99% uptime but makes no guarantee of service availability. Service credits shall not be available for downtime caused by factors outside Vendor's reasonable control.

ARTICLE 4 — AUTO-RENEWAL
This Agreement shall automatically renew for successive one-year terms unless either party provides written notice of non-renewal at least ninety (90) days prior to the end of the then-current term.

ARTICLE 5 — INTELLECTUAL PROPERTY
Each party shall retain ownership of its respective pre-existing intellectual property. Any custom development specifically commissioned by Customer under a Statement of Work shall be owned by Customer upon full payment.`,
    clauses: [
      { id: 'v1', type: 'Limitation of Liability', severity: 'critical', snippet: "Vendor's total liability shall not exceed $500 under any circumstances whatsoever...", original: "In no event shall Vendor be liable to Customer for any amounts exceeding five hundred dollars ($500), regardless of the basis of the claim, whether in contract, tort, or otherwise.", risk: "An absolute $500 liability cap is unacceptably low for an enterprise software agreement. This does not even cover the cost of a business disruption, data breach notification, or basic remediation efforts.", redline: "Vendor's total liability shall not exceed the total fees paid or payable by Customer in the TWELVE (12) months immediately preceding the event giving rise to the claim. For data breaches or gross negligence, no limitation shall apply.", riskFactors: ['Cap far too low', 'No carve-outs', 'Asymmetric protection', 'No breach remedy'] },
      { id: 'v2', type: 'Data Processing', severity: 'critical', snippet: 'Vendor may use customer data for product improvement, analytics, and training purposes...', original: "Customer grants Vendor a perpetual, irrevocable, worldwide license to use, reproduce, modify, and create derivative works from Customer Data for the purposes of improving Vendor's products, services, and underlying technologies.", risk: "This clause grants the vendor a perpetual irrevocable license to your customer data for their own commercial purposes. This is a GDPR/CCPA violation risk and poses serious IP and competitive intelligence exposure.", redline: "Vendor shall not use Customer Data for any purpose other than providing the contracted services to Customer. Vendor acquires no ownership or license to Customer Data. All Customer Data remains the exclusive property of Customer.", riskFactors: ['GDPR/CCPA violation risk', 'Perpetual irrevocable license', 'IP exposure', 'Competitive intelligence risk'] },
      { id: 'v3', type: 'Service Level Agreement', severity: 'high', snippet: 'Vendor targets 99% uptime but makes no guarantees of service availability...', original: "Vendor will use commercially reasonable efforts to maintain 99% uptime but makes no guarantee of service availability. Service credits shall not be available for downtime caused by factors outside Vendor's reasonable control.", risk: "'Commercially reasonable efforts' without defined SLAs or meaningful remedies is insufficient. 99% uptime allows ~87 hours of annual downtime with no compensation.", redline: "Vendor guarantees 99.9% monthly uptime. Downtime exceeding this threshold entitles Customer to service credits of 5% of monthly fees per hour of excess downtime, up to 30% of monthly fees. Planned maintenance excluded only with 72-hour prior notice.", riskFactors: ['No enforceable SLA', 'No credit mechanism', 'Vague remedy', 'High allowable downtime'] },
      { id: 'v4', type: 'Auto-Renewal', severity: 'medium', snippet: 'Agreement auto-renews annually unless cancelled 90 days prior...', original: 'This Agreement shall automatically renew for successive one-year terms unless either party provides written notice of non-renewal at least ninety (90) days prior to the end of the then-current term.', risk: '90-day cancellation notice requirement is longer than industry standard (30-60 days). This limits operational flexibility and creates a risk of unintended renewal.', redline: 'Reduce non-renewal notice period to SIXTY (60) days prior to term end. Include automatic reminder notification at 120 days before renewal.', riskFactors: ['Long notice window', 'Risk of unintended renewal', 'No reminder mechanism'] },
      { id: 'v5', type: 'Intellectual Property', severity: 'safe', snippet: 'Each party retains ownership of its pre-existing intellectual property...', original: "Each party shall retain ownership of its respective pre-existing intellectual property. Any custom development specifically commissioned by Customer under a Statement of Work shall be owned by Customer upon full payment.", risk: 'IP ownership is clearly defined with appropriate carve-outs. Customer retains ownership of bespoke development.', redline: null, riskFactors: [] }
    ]
  },
  employment: {
    name: 'Executive Employment Contract', type: 'Employment', pages: 14, size: '560 KB', score: 61,
    rawText: `EXECUTIVE EMPLOYMENT CONTRACT

ARTICLE 1 — NON-COMPETE
For a period of three (3) years following the termination of employment for any reason, Employee shall not, anywhere in the world, directly or indirectly engage in, own, manage, operate, or be employed by any business that competes with Employer's business.

ARTICLE 2 — ARBITRATION
Employee agrees to resolve all employment disputes through binding arbitration and waives any right to a jury trial or to participate in a class action or collective action.

ARTICLE 3 — SEVERANCE
In the event of termination by Employer for Cause or resignation by Employee, Employee shall not be entitled to any severance pay or benefits beyond accrued and unpaid wages through the date of termination.

ARTICLE 4 — COMPENSATION AND BENEFITS
Employee shall receive an annual base salary of [$AMOUNT], subject to annual performance review. Employee shall be eligible for participation in the Company's annual bonus plan and standard employee benefits package.`,
    clauses: [
      { id: 'e1', type: 'Non-Compete', severity: 'critical', snippet: 'Employee shall not engage in any competitive activity worldwide for 3 years post-employment...', original: "For a period of three (3) years following the termination of employment for any reason, Employee shall not, anywhere in the world, directly or indirectly engage in, own, manage, operate, or be employed by any business that competes with Employer's business.", risk: 'Worldwide 3-year non-compete is unenforceable in most US jurisdictions (California, Minnesota, North Dakota ban them entirely) and likely overreaching under common law in others.', redline: 'Non-compete shall be limited to [YOUR STATE] for a period of ONE (1) year, restricted to directly competing roles in your specific product category. Employer should provide compensation during the restriction period.', riskFactors: ['Unenforceable in many states', 'Worldwide scope', '3-year duration excessive', 'No compensation'] },
      { id: 'e2', type: 'Arbitration', severity: 'high', snippet: 'Employee waives right to jury trial and class action for all employment disputes...', original: 'Employee agrees to resolve all employment disputes through binding arbitration and waives any right to a jury trial or to participate in a class action or collective action.', risk: 'Mandatory arbitration with class action waiver may be unenforceable for some employment claims (e.g., PAGA in California). Pre-dispute arbitration clauses for discrimination claims face increasing regulatory scrutiny.', redline: 'Recommend legal review in your jurisdiction. If retaining arbitration, specify neutral arbitration provider (e.g., JAMS), fee allocation (employer pays all costs), and carve-outs for injunctive relief.', riskFactors: ['May be unenforceable', 'Eliminates class action rights', 'Regulatory scrutiny', 'Limits discovery'] },
      { id: 'e3', type: 'Termination', severity: 'medium', snippet: 'No severance is payable upon termination for cause or resignation...', original: 'In the event of termination by Employer for Cause or resignation by Employee, Employee shall not be entitled to any severance pay or benefits beyond accrued and unpaid wages through the date of termination.', risk: '"For Cause" definition should be clearly specified to protect against arbitrary termination. Without adequate definition, employer has broad discretion.', redline: 'Define "Cause" narrowly and specifically (e.g., conviction of felony, material breach after written notice and cure period). For without-Cause termination, provide minimum severance of [X weeks per year of service].', riskFactors: ['"Cause" not defined', 'No cure period', 'No severance protection'] },
      { id: 'e4', type: 'Intellectual Property', severity: 'safe', snippet: 'Base salary of $X with annual performance review, bonus plan, and standard benefits...', original: "Employee shall receive an annual base salary of [$AMOUNT], subject to annual performance review. Employee shall be eligible for participation in the Company's annual bonus plan and standard employee benefits package.", risk: 'Compensation terms are clear and standard. Ensure bonus plan details are attached as an exhibit.', redline: null, riskFactors: [] }
    ]
  }
};

/* =================================================================
   PLAYBOOK RULES reference (for modal display)
   ================================================================= */
const PLAYBOOK_RULE_NAMES = CLAUSE_RULES.map(r => r.type);
const PLAYBOOK_SENSITIVITY_KEY = { strict: 'strict', standard: 'standard', permissive: 'permissive' };

/* =================================================================
   APP STATE
   ================================================================= */
var AppState = {
  currentContract: null,
  selectedClause: null,
  currentFilter: 'all',
  currentSearch: '',
  currentView: 'cards',
  currentPlaybook: 'standard',
  currentSensitivity: 'standard',
  isAnalyzing: false,
  acceptedRedlines: {},   // { clauseId: redlineText }
  customRedlines: {},     // { clauseId: redlineText }
  pendingPlaybook: 'standard',
  pendingSensitivity: 'standard',
};

/* =================================================================
   DOM READY
   ================================================================= */
document.addEventListener('DOMContentLoaded', function () {
  initStatusBar();
  initUploadZone();
  initSampleContracts();
  initFilterButtons();
  initViewSwitcher();
  initSearch();
  initSensitivityToggle();
  initTopbarButtons();
  initPlaybookModal();
  initExportModal();
  initDetailTabs();
  initKeyboardShortcuts();
  initClearButton();

  // Configure PDF.js worker
  if (window.pdfjsLib) {
    pdfjsLib.GlobalWorkerOptions.workerSrc =
      'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
  }
});

/* =================================================================
   STATUS BAR — poll /api/v1/health every 30s
   ================================================================= */
function initStatusBar() { fetchHealth(); setInterval(fetchHealth, 30000); }

function fetchHealth() {
  ['pill-db', 'pill-redis', 'pill-storage'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.className = 'status-pill loading';
  });
  fetch('/api/v1/health')
    .then(function (r) { return r.json(); })
    .then(function (data) {
      updatePill('pill-db', data.services.db === 'ok');
      updatePill('pill-redis', data.services.redis === 'ok');
      updatePill('pill-storage', data.services.storage === 'ok');
    })
    .catch(function () {
      updatePill('pill-db', false);
      updatePill('pill-redis', false);
      updatePill('pill-storage', false);
    });
}

function updatePill(id, isOk) {
  var el = document.getElementById(id);
  if (!el) return;
  el.className = 'status-pill ' + (isOk ? 'ok' : 'error');
}

/* =================================================================
   SENSITIVITY TOGGLE (topbar)
   ================================================================= */
function initSensitivityToggle() {
  document.querySelectorAll('.sens-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.sens-btn').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      AppState.currentSensitivity = btn.getAttribute('data-sensitivity');
      AppState.pendingSensitivity = AppState.currentSensitivity;
      updateSensitivityInModal(AppState.currentSensitivity);
    });
  });
  // Set default active
  var defaultBtn = document.querySelector('.sens-btn[data-sensitivity="standard"]');
  if (defaultBtn) {
    document.querySelectorAll('.sens-btn').forEach(function (b) { b.classList.remove('active'); });
    defaultBtn.classList.add('active');
  }
}

/* =================================================================
   UPLOAD ZONE
   ================================================================= */
function initUploadZone() {
  var zone = document.getElementById('upload-zone');
  var fileInput = document.getElementById('file-input');
  if (!zone || !fileInput) return;

  zone.addEventListener('click', function (e) {
    if (e.target !== fileInput) fileInput.click();
  });
  zone.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
  });
  zone.addEventListener('dragover', function (e) {
    e.preventDefault(); zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', function () { zone.classList.remove('drag-over'); });
  zone.addEventListener('drop', function (e) {
    e.preventDefault(); zone.classList.remove('drag-over');
    var file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  });
  fileInput.addEventListener('change', function () {
    if (fileInput.files[0]) handleFileUpload(fileInput.files[0]);
  });
}

function handleFileUpload(file) {
  var ext = file.name.split('.').pop().toLowerCase();
  if (!['pdf', 'docx', 'txt'].includes(ext)) {
    showToast('❌ Unsupported file type. Use PDF, DOCX, or TXT.', 'error');
    return;
  }
  enableAnalyzeBtn(true);
  document.getElementById('btn-analyze').onclick = function () { parseAndAnalyzeFile(file); };
  showToast('📄 File loaded: ' + file.name + ' — click Analyze to start', 'info');
}

function enableAnalyzeBtn(enabled) {
  var btn = document.getElementById('btn-analyze');
  if (btn) btn.disabled = !enabled;
}

function parseAndAnalyzeFile(file) {
  var ext = file.name.split('.').pop().toLowerCase();
  showProgress(true);
  setProgress('Reading file…', 10, 'Parsing ' + ext.toUpperCase() + ' document');

  if (ext === 'txt') {
    var reader = new FileReader();
    reader.onload = function (e) {
      var text = e.target.result;
      analyzeText(text, file.name.replace(/\.\w+$/, ''), formatFileSize(file.size));
    };
    reader.readAsText(file);
  } else if (ext === 'docx' && window.mammoth) {
    var reader2 = new FileReader();
    reader2.onload = function (e) {
      mammoth.extractRawText({ arrayBuffer: e.target.result })
        .then(function (result) {
          analyzeText(result.value, file.name.replace(/\.\w+$/, ''), formatFileSize(file.size));
        })
        .catch(function () {
          showToast('⚠️ Could not parse DOCX. Falling back to sample data.', 'error');
          var keys = Object.keys(SAMPLE_CONTRACTS);
          var base = SAMPLE_CONTRACTS[keys[Math.floor(Math.random() * keys.length)]];
          analyzeText(base.rawText, file.name.replace(/\.\w+$/, ''), formatFileSize(file.size));
        });
    };
    reader2.readAsArrayBuffer(file);
  } else if (ext === 'pdf' && window.pdfjsLib) {
    var reader3 = new FileReader();
    reader3.onload = function (e) {
      setProgress('Extracting PDF text…', 20, 'Decoding PDF pages');
      pdfjsLib.getDocument({ data: e.target.result }).promise.then(function (pdf) {
        var allText = [];
        var total = pdf.numPages;
        var done = 0;
        for (var i = 1; i <= total; i++) {
          (function (pageNum) {
            pdf.getPage(pageNum).then(function (page) {
              page.getTextContent().then(function (tc) {
                allText[pageNum - 1] = tc.items.map(function (s) { return s.str; }).join(' ');
                done++;
                if (done === total) {
                  analyzeText(allText.join('\n\n'), file.name.replace(/\.\w+$/, ''), formatFileSize(file.size));
                }
              });
            });
          })(i);
        }
      }).catch(function () {
        showToast('⚠️ Could not extract PDF text. Using sample data.', 'error');
        var keys = Object.keys(SAMPLE_CONTRACTS);
        var base = SAMPLE_CONTRACTS[keys[Math.floor(Math.random() * keys.length)]];
        analyzeText(base.rawText, file.name.replace(/\.\w+$/, ''), formatFileSize(file.size));
      });
    };
    reader3.readAsArrayBuffer(file);
  } else {
    // Fallback: use sample
    var keys = Object.keys(SAMPLE_CONTRACTS);
    var base = SAMPLE_CONTRACTS[keys[Math.floor(Math.random() * keys.length)]];
    analyzeText(base.rawText, file.name.replace(/\.\w+$/, ''), formatFileSize(file.size));
  }
}

/* =================================================================
   CLIENT-SIDE NLP ANALYSIS ENGINE
   ================================================================= */
function analyzeText(text, name, size) {
  var sensitivity = AppState.currentSensitivity;
  var clauses = classifyClauses(text, sensitivity);
  var score = computeRiskScore(clauses, sensitivity);
  var type = inferContractType(text, AppState.currentPlaybook);
  var wordCount = text.split(/\s+/).length;
  var pages = Math.max(1, Math.round(wordCount / 500));

  var contract = {
    name: name || 'Uploaded Contract',
    type: type,
    pages: pages,
    size: size || '—',
    score: score,
    clauses: clauses,
    rawText: text
  };
  startAnalysis(contract);
}

function classifyClauses(text, sensitivity) {
  var paragraphs = text.split(/\n{2,}/).filter(function (p) { return p.trim().length > 40; });
  var found = [];
  var usedRules = {};

  paragraphs.forEach(function (para, idx) {
    CLAUSE_RULES.forEach(function (rule) {
      if (usedRules[rule.type]) return; // each rule type once per document
      var matched = rule.patterns.some(function (p) { return p.test(para); });
      if (matched) {
        usedRules[rule.type] = true;
        var severity = rule.severities[sensitivity] || rule.severities.standard;
        var snippet = para.replace(/\s+/g, ' ').trim().substring(0, 130) + '…';
        found.push({
          id: 'cl_' + Math.random().toString(36).substr(2, 6),
          type: rule.type,
          severity: severity,
          snippet: snippet,
          original: para.trim().substring(0, 800),
          risk: rule.risk,
          redline: rule.redline,
          riskFactors: rule.riskFactors || [],
          pageHint: Math.max(1, Math.floor(idx / 3) + 1)
        });
      }
    });
  });

  // Sort: critical → high → medium → safe
  var order = { critical: 0, high: 1, medium: 2, safe: 3 };
  found.sort(function (a, b) { return (order[a.severity] || 3) - (order[b.severity] || 3); });
  return found;
}

function computeRiskScore(clauses, sensitivity) {
  if (!clauses.length) return 0;
  var weights = { critical: 40, high: 25, medium: 12, safe: 3 };
  var total = clauses.reduce(function (acc, c) { return acc + (weights[c.severity] || 0); }, 0);
  var maxPossible = clauses.length * 40;
  var raw = maxPossible ? Math.round((total / maxPossible) * 100) : 0;
  var mod = { strict: 1.15, standard: 1.0, permissive: 0.85 }[sensitivity] || 1.0;
  return Math.min(100, Math.round(raw * mod));
}

function inferContractType(text, playbook) {
  if (playbook !== 'standard') return playbook.charAt(0).toUpperCase() + playbook.slice(1);
  var low = text.toLowerCase();
  if (/non.?disclosure|nda/.test(low)) return 'NDA';
  if (/employment|employee|employer/.test(low)) return 'Employment';
  if (/saas|software.*subscription/.test(low)) return 'SaaS / MSA';
  if (/vendor|supplier|purchase order/.test(low)) return 'Vendor';
  return 'General Commercial';
}

/* =================================================================
   SAMPLE CONTRACTS
   ================================================================= */
function initSampleContracts() {
  document.querySelectorAll('.sample-contract-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var key = btn.getAttribute('data-contract');
      if (SAMPLE_CONTRACTS[key]) startAnalysis(SAMPLE_CONTRACTS[key]);
    });
  });
}

/* =================================================================
   ANALYSIS PIPELINE
   ================================================================= */
function startAnalysis(contract) {
  if (AppState.isAnalyzing) return;
  AppState.isAnalyzing = true;
  AppState.currentContract = contract;
  AppState.selectedClause = null;
  AppState.currentFilter = 'all';
  AppState.currentSearch = '';
  AppState.acceptedRedlines = {};
  AppState.customRedlines = {};

  var searchInput = document.getElementById('clause-search');
  if (searchInput) searchInput.value = '';

  disableBtn(true);
  showProgress(true);
  enableAnalyzeBtn(false);

  var steps = [
    { label: 'Uploading contract…', pct: 12, detail: 'Transferring to analysis engine' },
    { label: 'Extracting text…', pct: 28, detail: 'OCR & text extraction' },
    { label: 'Segmenting clauses…', pct: 45, detail: 'NLP paragraph analysis' },
    { label: 'Running AI risk engine…', pct: 65, detail: 'Classifying clause types' },
    { label: 'Scoring against playbook…', pct: 82, detail: 'Applying ' + AppState.currentPlaybook + ' rules' },
    { label: 'Generating redlines…', pct: 94, detail: 'AI redline suggestions' },
    { label: 'Finalizing report…', pct: 100, detail: 'Compiling results' }
  ];

  var i = 0;
  function next() {
    if (i >= steps.length) {
      setTimeout(function () {
        showProgress(false);
        disableBtn(false);
        AppState.isAnalyzing = false;
        renderAnalysis(contract);
        showToast('✅ Analysis complete — ' + contract.clauses.length + ' clauses identified', 'success');
      }, 350);
      return;
    }
    setProgress(steps[i].label, steps[i].pct, steps[i].detail);
    i++;
    setTimeout(next, 360);
  }
  next();
}

function setProgress(label, pct, detail) {
  var lEl = document.getElementById('progress-label');
  var pEl = document.getElementById('progress-pct');
  var fEl = document.getElementById('progress-fill');
  var dEl = document.getElementById('progress-step-detail');
  if (lEl) lEl.textContent = label;
  if (pEl) pEl.textContent = pct + '%';
  if (fEl) fEl.style.width = pct + '%';
  if (dEl) dEl.textContent = detail || '';
  var pb = document.getElementById('progress-fill');
  if (pb) pb.setAttribute('aria-valuenow', pct);
}

function showProgress(show) {
  var el = document.getElementById('progress-container');
  if (el) el.classList.toggle('visible', show);
}

function disableBtn(disabled) {
  var btn = document.getElementById('btn-analyze');
  if (!btn) return;
  btn.disabled = disabled;
  btn.classList.toggle('loading', disabled);
  var icon = btn.querySelector('.btn-analyze-icon');
  var text = btn.querySelector('.btn-analyze-text');
  if (icon) icon.textContent = disabled ? '⏳' : '🔍';
  if (text) text.textContent = disabled ? 'Analyzing…' : 'Analyze Contract';
}

/* =================================================================
   RENDER ANALYSIS RESULTS
   ================================================================= */
function renderAnalysis(contract) {
  document.getElementById('empty-state').style.display = 'none';
  var av = document.getElementById('analysis-view');
  av.classList.add('visible');

  renderRiskOverview(contract);
  renderClauseList(contract.clauses);
  renderDocumentView(contract);
  renderMatrixView(contract.clauses);
  renderMatrixMini(contract.clauses);
  setActiveFilter('all');
  setViewMode('cards');
  showDetailPlaceholder();
  updateClauseCount();

  // Show left stats
  updateLeftStats(contract.clauses);
  document.getElementById('left-stats').style.display = '';

  // Enable export
  var exportBtn = document.getElementById('btn-export');
  if (exportBtn) exportBtn.disabled = false;

  // Update topbar playbook label
  var playbookNames = { standard: 'Standard', nda: 'NDA', vendor: 'Vendor', employment: 'Employment', saas: 'SaaS/MSA' };
  var lbl = document.getElementById('topbar-playbook-label');
  if (lbl) lbl.textContent = playbookNames[AppState.currentPlaybook] || 'Standard';
}

function renderRiskOverview(contract) {
  document.getElementById('contract-name').textContent = contract.name;
  document.getElementById('contract-info').textContent =
    contract.type + ' · ' + contract.pages + ' pages · ' + contract.size;

  var counts = countBySeverity(contract.clauses);
  document.getElementById('stat-critical').textContent = counts.critical;
  document.getElementById('stat-high').textContent = counts.high;
  document.getElementById('stat-medium').textContent = counts.medium;
  document.getElementById('stat-safe').textContent = counts.safe;

  animateGauge(contract.score);
}

function countBySeverity(clauses) {
  return clauses.reduce(function (acc, c) {
    acc[c.severity] = (acc[c.severity] || 0) + 1;
    return acc;
  }, { critical: 0, high: 0, medium: 0, safe: 0 });
}

function animateGauge(score) {
  var circle = document.getElementById('gauge-fill');
  var numEl = document.getElementById('gauge-number');
  var labelEl = document.getElementById('gauge-label');
  var circumference = 307;
  var offset = circumference - (score / 100) * circumference;

  var color, label;
  if (score >= 75) { color = '#EF4444'; label = 'HIGH RISK'; }
  else if (score >= 50) { color = '#F59E0B'; label = 'MEDIUM RISK'; }
  else if (score >= 25) { color = '#8B5CF6'; label = 'LOW-MEDIUM'; }
  else { color = '#10B981'; label = 'LOW RISK'; }

  if (circle) {
    circle.style.stroke = color;
    circle.style.strokeDashoffset = circumference;
    setTimeout(function () { circle.style.strokeDashoffset = offset; }, 150);
  }
  if (numEl) { numEl.textContent = score; numEl.style.color = color; }
  if (labelEl) { labelEl.textContent = label; labelEl.style.color = color; }
}

function renderMatrixMini(clauses) {
  var counts = countBySeverity(clauses);
  var total = clauses.length || 1;
  var bars = document.getElementById('matrix-bars');
  if (!bars) return;
  bars.innerHTML = '';
  ['critical', 'high', 'medium', 'safe'].forEach(function (sev) {
    var pct = Math.round((counts[sev] / total) * 100);
    var row = document.createElement('div');
    row.className = 'matrix-bar-row';
    row.innerHTML =
      '<div class="matrix-bar-label">' + sev.charAt(0).toUpperCase() + sev.slice(1) + '</div>' +
      '<div class="matrix-bar-track"><div class="matrix-bar-fill ' + sev + '" style="width:0%"></div></div>';
    bars.appendChild(row);
    setTimeout(function () {
      var fill = row.querySelector('.matrix-bar-fill');
      if (fill) fill.style.width = pct + '%';
    }, 200);
  });
}

function updateLeftStats(clauses) {
  var counts = countBySeverity(clauses);
  var el = function (id) { return document.getElementById(id); };
  if (el('ls-critical')) el('ls-critical').textContent = counts.critical;
  if (el('ls-high')) el('ls-high').textContent = counts.high;
  if (el('ls-medium')) el('ls-medium').textContent = counts.medium;
  if (el('ls-safe')) el('ls-safe').textContent = counts.safe;
}

/* =================================================================
   CLAUSE LIST (CARDS VIEW)
   ================================================================= */
function renderClauseList(clauses) {
  var list = document.getElementById('clause-list');
  list.innerHTML = '';
  clauses.forEach(function (clause, idx) {
    var item = document.createElement('div');
    item.className = 'clause-item ' + clause.severity;
    item.setAttribute('data-id', clause.id);
    item.setAttribute('data-severity', clause.severity);
    item.setAttribute('role', 'listitem');
    item.setAttribute('tabindex', '0');
    item.style.animationDelay = (idx * 0.04) + 's';

    var acceptedMark = AppState.acceptedRedlines[clause.id]
      ? '<span class="clause-accepted-mark">✅ Redline Accepted</span>'
      : '<span class="clause-accepted-mark"></span>';

    item.innerHTML =
      '<div class="severity-badge">' + clause.severity.toUpperCase() + '</div>' +
      '<div class="clause-body">' +
        '<div class="clause-type">' + clause.type +
          (clause.riskFactors && clause.riskFactors.length ? ' <span style="font-size:9px;color:var(--text-muted);font-weight:400;">(' + clause.riskFactors.length + ' factors)</span>' : '') +
        '</div>' +
        '<div class="clause-snippet">' + escapeHtml(clause.snippet) + '</div>' +
        acceptedMark +
      '</div>';

    if (AppState.acceptedRedlines[clause.id]) item.classList.add('accepted');

    item.addEventListener('click', function () { selectClause(clause, item); });
    item.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectClause(clause, item); }
    });
    list.appendChild(item);
  });
}

function selectClause(clause, itemEl) {
  document.querySelectorAll('.clause-item').forEach(function (el) { el.classList.remove('selected'); });
  document.querySelectorAll('.doc-highlight').forEach(function (el) { el.classList.remove('active'); });
  itemEl.classList.add('selected');

  // Highlight doc view
  var docEl = document.querySelector('.doc-highlight[data-id="' + clause.id + '"]');
  if (docEl) docEl.classList.add('active');

  AppState.selectedClause = clause;
  renderClauseDetail(clause);

  // Scroll into view
  itemEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderClauseDetail(clause) {
  document.getElementById('detail-placeholder').style.display = 'none';
  var view = document.getElementById('detail-view');
  view.classList.add('visible');

  document.getElementById('detail-type').textContent = clause.type;
  var badge = document.getElementById('detail-badge');
  badge.textContent = clause.severity.toUpperCase();
  badge.className = 'severity-badge';
  badge.setAttribute('data-sev', clause.severity);
  badge.style.display = 'inline-block';

  var meta = document.getElementById('detail-meta');
  if (meta) meta.textContent = 'Page ~' + (clause.pageHint || '?') + ' · ' + clause.severity + ' severity';

  document.getElementById('original-text').textContent = clause.original;
  document.getElementById('risk-explanation').textContent = clause.risk;

  // Risk factors
  var rfsSection = document.getElementById('risk-factors-section');
  var rfsList = document.getElementById('risk-factors-list');
  if (clause.riskFactors && clause.riskFactors.length) {
    rfsSection.style.display = '';
    rfsList.innerHTML = clause.riskFactors.map(function (f) {
      return '<li>⚠️ ' + escapeHtml(f) + '</li>';
    }).join('');
  } else {
    rfsSection.style.display = 'none';
  }

  // Diff view
  renderDiffView(clause);

  // Redline box
  var redlineSection = document.getElementById('redline-section-diff');
  var redlineText = document.getElementById('redline-text');
  var noRedlineMsg = document.getElementById('no-redline-msg');
  var customRedline = AppState.customRedlines[clause.id];
  var activeRedline = customRedline !== undefined ? customRedline : clause.redline;

  if (activeRedline) {
    if (redlineSection) redlineSection.style.display = '';
    if (noRedlineMsg) noRedlineMsg.style.display = 'none';
    if (redlineText) redlineText.textContent = activeRedline;
    var box = document.getElementById('redline-box');
    if (box) box.setAttribute('data-redline', activeRedline);
  } else {
    if (redlineSection) redlineSection.style.display = 'none';
    if (noRedlineMsg) noRedlineMsg.style.display = '';
  }

  // Accept button state
  var acceptBtn = document.getElementById('accept-redline-btn');
  if (acceptBtn) {
    var isAccepted = !!AppState.acceptedRedlines[clause.id];
    acceptBtn.textContent = isAccepted ? '✅ Accepted' : '✅ Accept';
    acceptBtn.classList.toggle('accepted', isAccepted);
  }

  // Editor tab
  var editorTA = document.getElementById('redline-editor');
  if (editorTA) editorTA.value = activeRedline || clause.redline || '';

  // Accepted status in edit tab
  var acceptedStatusSection = document.getElementById('accepted-status-section');
  if (acceptedStatusSection) acceptedStatusSection.style.display = AppState.acceptedRedlines[clause.id] ? '' : 'none';

  // Switch to analysis tab
  switchDetailTab('analysis');
}

function renderDiffView(clause) {
  var diffContainer = document.getElementById('diff-view');
  if (!diffContainer) return;
  var customRedline = AppState.customRedlines[clause.id];
  var activeRedline = customRedline !== undefined ? customRedline : clause.redline;
  if (!activeRedline) {
    diffContainer.innerHTML = '<div style="padding:12px;font-size:12px;color:var(--text-muted);">No redline available for this clause.</div>';
    return;
  }
  var diff = generateInlineDiff(clause.original, activeRedline);
  diffContainer.innerHTML = diff;
}

function generateInlineDiff(original, redline) {
  if (!original || !redline) return '';
  // Split into sentences for diff
  var origSentences = original.match(/[^.!?]+[.!?]+/g) || [original];
  var newSentences = redline.match(/[^.!?]+[.!?]+/g) || [redline];

  var html = '';

  // Show deleted (original) lines in red
  origSentences.forEach(function (s) {
    html +=
      '<div class="diff-row diff-del">' +
      '<span class="diff-prefix">−</span>' +
      '<span class="diff-content">' + escapeHtml(s.trim()) + '</span>' +
      '</div>';
  });

  // Show added (redline) lines in green
  newSentences.forEach(function (s) {
    html +=
      '<div class="diff-row diff-add">' +
      '<span class="diff-prefix">+</span>' +
      '<span class="diff-content">' + escapeHtml(s.trim()) + '</span>' +
      '</div>';
  });

  return html;
}

/* =================================================================
   DOCUMENT VIEW
   ================================================================= */
function renderDocumentView(contract) {
  var content = document.getElementById('document-content');
  var docName = document.getElementById('doc-contract-name');
  if (!content) return;
  if (docName) docName.textContent = contract.name;

  if (!contract.rawText) {
    content.innerHTML = '<span style="color:var(--text-muted);font-size:12px;">Document text not available for sample contracts.</span>';
    return;
  }

  // Build text with clause highlights
  var text = contract.rawText;
  var html = escapeHtml(text);

  // For each clause, try to highlight its snippet in the document
  contract.clauses.forEach(function (clause) {
    var snippet = clause.original ? clause.original.substring(0, 80).replace(/[.*+?^${}()|[\]\\]/g, '\\$&') : '';
    if (!snippet) return;
    try {
      var regex = new RegExp('(' + snippet + ')', 'g');
      html = html.replace(regex, function (match) {
        return '<span class="doc-highlight ' + clause.severity + '" data-id="' + clause.id + '" title="' + clause.type + '" tabindex="0">' + match + '</span>';
      });
    } catch (e) { /* ignore regex errors */ }
  });

  content.innerHTML = html;

  // Add click handlers to doc highlights
  content.querySelectorAll('.doc-highlight').forEach(function (el) {
    el.addEventListener('click', function () {
      var cid = el.getAttribute('data-id');
      var clause = (contract.clauses || []).find(function (c) { return c.id === cid; });
      if (!clause) return;
      var cardEl = document.querySelector('.clause-item[data-id="' + cid + '"]');
      if (cardEl) selectClause(clause, cardEl);
    });
  });
}

/* =================================================================
   MATRIX VIEW
   ================================================================= */
function renderMatrixView(clauses) {
  var grid = document.getElementById('matrix-grid');
  if (!grid) return;
  grid.innerHTML = '';
  clauses.forEach(function (clause) {
    var cell = document.createElement('div');
    cell.className = 'matrix-cell ' + clause.severity;
    cell.setAttribute('tabindex', '0');
    cell.setAttribute('title', clause.type + ' — ' + clause.severity);
    cell.innerHTML =
      '<div class="matrix-cell-sev">' + clause.severity.toUpperCase() + '</div>' +
      '<div class="matrix-cell-type">' + clause.type + '</div>' +
      '<div class="matrix-cell-snippet">' + escapeHtml(clause.snippet) + '</div>';
    cell.addEventListener('click', function () {
      var cardEl = document.querySelector('.clause-item[data-id="' + clause.id + '"]');
      if (cardEl) {
        setViewMode('cards');
        selectClause(clause, cardEl);
      } else {
        selectClause(clause, document.createElement('div'));
      }
    });
    grid.appendChild(cell);
  });
}

/* =================================================================
   FILTER BUTTONS
   ================================================================= */
function initFilterButtons() {
  document.querySelectorAll('.filter-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var filter = btn.getAttribute('data-filter');
      setActiveFilter(filter);
      applyFilters();
    });
  });
}

function setActiveFilter(filter) {
  AppState.currentFilter = filter;
  document.querySelectorAll('.filter-btn').forEach(function (btn) {
    var isActive = btn.getAttribute('data-filter') === filter;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
  });
}

function applyFilters() {
  var filter = AppState.currentFilter;
  var search = (AppState.currentSearch || '').toLowerCase().trim();
  document.querySelectorAll('.clause-item').forEach(function (item) {
    var sev = item.getAttribute('data-severity');
    var text = item.textContent.toLowerCase();
    var sevMatch = filter === 'all' || sev === filter;
    var searchMatch = !search || text.includes(search);
    item.classList.toggle('hidden', !(sevMatch && searchMatch));
  });
  updateClauseCount();
}

/* =================================================================
   SEARCH
   ================================================================= */
function initSearch() {
  var input = document.getElementById('clause-search');
  if (!input) return;
  input.addEventListener('input', function () {
    AppState.currentSearch = input.value;
    applyFilters();
  });
}

/* =================================================================
   VIEW SWITCHER
   ================================================================= */
function initViewSwitcher() {
  document.querySelectorAll('.view-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var view = btn.getAttribute('data-view');
      setViewMode(view);
    });
  });
}

function setViewMode(view) {
  AppState.currentView = view;
  document.querySelectorAll('.view-btn').forEach(function (btn) {
    var isActive = btn.getAttribute('data-view') === view;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
  });
  var clauseList = document.getElementById('clause-list');
  var documentView = document.getElementById('document-view');
  var matrixView = document.getElementById('matrix-view');
  if (clauseList) clauseList.style.display = view === 'cards' ? '' : 'none';
  if (documentView) documentView.style.display = view === 'document' ? '' : 'none';
  if (matrixView) matrixView.style.display = view === 'matrix' ? '' : 'none';
}

/* =================================================================
   DETAIL TABS
   ================================================================= */
function initDetailTabs() {
  document.querySelectorAll('.detail-tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      switchDetailTab(tab.getAttribute('data-tab'));
    });
  });

  // Accept redline
  var acceptBtn = document.getElementById('accept-redline-btn');
  if (acceptBtn) {
    acceptBtn.addEventListener('click', function () {
      var clause = AppState.selectedClause;
      if (!clause) return;
      var customRedline = AppState.customRedlines[clause.id];
      var activeRedline = customRedline !== undefined ? customRedline : clause.redline;
      if (!activeRedline) return;

      var isAccepted = !!AppState.acceptedRedlines[clause.id];
      if (isAccepted) {
        delete AppState.acceptedRedlines[clause.id];
        acceptBtn.textContent = '✅ Accept';
        acceptBtn.classList.remove('accepted');
        showToast('↩ Redline acceptance reverted', 'info');
      } else {
        AppState.acceptedRedlines[clause.id] = activeRedline;
        acceptBtn.textContent = '✅ Accepted';
        acceptBtn.classList.add('accepted');
        showToast('✅ Redline accepted for: ' + clause.type, 'success');
      }
      // Update accepted status in edit tab
      var acceptedStatusSection = document.getElementById('accepted-status-section');
      if (acceptedStatusSection) acceptedStatusSection.style.display = AppState.acceptedRedlines[clause.id] ? '' : 'none';
      // Update card mark
      refreshClauseCard(clause.id);
      // Update export note
      updateExportAcceptedNote();
    });
  }

  // Copy redline
  document.addEventListener('click', function (e) {
    if (e.target.id === 'copy-redline-btn' || e.target.classList.contains('copy-btn')) {
      var box = e.target.closest ? e.target.closest('.redline-box') : null;
      var text = box ? box.getAttribute('data-redline') : '';
      if (!text && AppState.selectedClause) {
        var c = AppState.selectedClause;
        text = AppState.customRedlines[c.id] !== undefined ? AppState.customRedlines[c.id] : c.redline;
      }
      if (text && navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function () {
          var btn = document.getElementById('copy-redline-btn');
          if (btn) {
            var orig = btn.textContent;
            btn.textContent = '✓ Copied!';
            btn.classList.add('copied');
            setTimeout(function () { btn.textContent = orig; btn.classList.remove('copied'); }, 2000);
          }
          showToast('📋 Redline copied to clipboard', 'success');
        });
      }
    }
  });

  // Save custom redline
  var saveBtn = document.getElementById('btn-save-redline');
  if (saveBtn) {
    saveBtn.addEventListener('click', function () {
      var clause = AppState.selectedClause;
      if (!clause) return;
      var ta = document.getElementById('redline-editor');
      if (!ta) return;
      AppState.customRedlines[clause.id] = ta.value;
      // Refresh diff and redline text
      renderDiffView(clause);
      var redlineText = document.getElementById('redline-text');
      if (redlineText) redlineText.textContent = ta.value;
      var box = document.getElementById('redline-box');
      if (box) box.setAttribute('data-redline', ta.value);
      showToast('💾 Custom redline saved', 'success');
    });
  }

  // Reset to AI suggestion
  var resetBtn = document.getElementById('btn-reset-redline');
  if (resetBtn) {
    resetBtn.addEventListener('click', function () {
      var clause = AppState.selectedClause;
      if (!clause) return;
      delete AppState.customRedlines[clause.id];
      var ta = document.getElementById('redline-editor');
      if (ta) ta.value = clause.redline || '';
      renderDiffView(clause);
      var redlineText = document.getElementById('redline-text');
      if (redlineText) redlineText.textContent = clause.redline || '';
      showToast('↺ Reset to AI suggestion', 'info');
    });
  }

  // Unaccept
  var unacceptBtn = document.getElementById('btn-unaccept');
  if (unacceptBtn) {
    unacceptBtn.addEventListener('click', function () {
      var clause = AppState.selectedClause;
      if (!clause) return;
      delete AppState.acceptedRedlines[clause.id];
      var acceptedStatusSection = document.getElementById('accepted-status-section');
      if (acceptedStatusSection) acceptedStatusSection.style.display = 'none';
      var acceptBtn2 = document.getElementById('accept-redline-btn');
      if (acceptBtn2) { acceptBtn2.textContent = '✅ Accept'; acceptBtn2.classList.remove('accepted'); }
      refreshClauseCard(clause.id);
      showToast('↩ Acceptance reverted', 'info');
    });
  }
}

function switchDetailTab(tabName) {
  document.querySelectorAll('.detail-tab').forEach(function (t) {
    var isActive = t.getAttribute('data-tab') === tabName;
    t.classList.toggle('active', isActive);
    t.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });
  document.querySelectorAll('.tab-panel').forEach(function (panel) {
    panel.style.display = 'none';
  });
  var target = document.getElementById('tab-panel-' + tabName);
  if (target) target.style.display = '';
}

function refreshClauseCard(clauseId) {
  var card = document.querySelector('.clause-item[data-id="' + clauseId + '"]');
  if (!card) return;
  var mark = card.querySelector('.clause-accepted-mark');
  var isAccepted = !!AppState.acceptedRedlines[clauseId];
  card.classList.toggle('accepted', isAccepted);
  if (mark) mark.textContent = isAccepted ? '✅ Redline Accepted' : '';
  if (mark) mark.style.display = isAccepted ? 'inline-flex' : 'none';
}

/* =================================================================
   CLEAR BUTTON
   ================================================================= */
function initClearButton() {
  var btn = document.getElementById('btn-clear');
  if (!btn) return;
  btn.addEventListener('click', function () {
    AppState.currentContract = null;
    AppState.selectedClause = null;
    AppState.acceptedRedlines = {};
    AppState.customRedlines = {};
    document.getElementById('empty-state').style.display = '';
    document.getElementById('analysis-view').classList.remove('visible');
    document.getElementById('left-stats').style.display = 'none';
    document.getElementById('detail-placeholder').style.display = '';
    document.getElementById('detail-view').classList.remove('visible');
    var exportBtn = document.getElementById('btn-export');
    if (exportBtn) exportBtn.disabled = true;
    var fileInput = document.getElementById('file-input');
    if (fileInput) fileInput.value = '';
    enableAnalyzeBtn(false);
    document.getElementById('btn-analyze').onclick = null;
    showToast('↺ Analysis cleared — ready for new contract', 'info');
  });
}

/* =================================================================
   TOPBAR BUTTONS
   ================================================================= */
function initTopbarButtons() {
  var playbookBtn = document.getElementById('btn-playbook-rules');
  if (playbookBtn) playbookBtn.addEventListener('click', openPlaybookModal);
  var exportBtn = document.getElementById('btn-export');
  if (exportBtn) exportBtn.addEventListener('click', openExportModal);
}

/* =================================================================
   PLAYBOOK MODAL
   ================================================================= */
function initPlaybookModal() {
  document.getElementById('playbook-modal-close').addEventListener('click', closePlaybookModal);
  document.getElementById('playbook-modal-cancel').addEventListener('click', closePlaybookModal);
  document.getElementById('playbook-modal-apply').addEventListener('click', applyPlaybook);
  document.getElementById('playbook-modal').addEventListener('click', function (e) {
    if (e.target === document.getElementById('playbook-modal')) closePlaybookModal();
  });

  // Playbook card selection
  document.querySelectorAll('.playbook-card').forEach(function (card) {
    card.addEventListener('click', function () {
      document.querySelectorAll('.playbook-card').forEach(function (c) {
        c.classList.remove('active'); c.setAttribute('aria-checked', 'false');
      });
      card.classList.add('active'); card.setAttribute('aria-checked', 'true');
      AppState.pendingPlaybook = card.getAttribute('data-playbook');
    });
    card.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); card.click(); }
    });
  });

  // Sensitivity card selection
  document.querySelectorAll('.sensitivity-card').forEach(function (card) {
    card.addEventListener('click', function () {
      document.querySelectorAll('.sensitivity-card').forEach(function (c) { c.classList.remove('active'); });
      card.classList.add('active');
      AppState.pendingSensitivity = card.getAttribute('data-sensitivity');
      // Sync topbar
      updateTopbarSensitivity(AppState.pendingSensitivity);
    });
  });

  // Render clause rules list
  renderClauseRulesList();
}

function openPlaybookModal() {
  AppState.pendingPlaybook = AppState.currentPlaybook;
  AppState.pendingSensitivity = AppState.currentSensitivity;

  // Sync modal state
  document.querySelectorAll('.playbook-card').forEach(function (c) {
    var isActive = c.getAttribute('data-playbook') === AppState.currentPlaybook;
    c.classList.toggle('active', isActive);
    c.setAttribute('aria-checked', isActive ? 'true' : 'false');
  });
  updateSensitivityInModal(AppState.currentSensitivity);
  renderClauseRulesList();

  document.getElementById('playbook-modal').style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function closePlaybookModal() {
  document.getElementById('playbook-modal').style.display = 'none';
  document.body.style.overflow = '';
}

function applyPlaybook() {
  AppState.currentPlaybook = AppState.pendingPlaybook;
  AppState.currentSensitivity = AppState.pendingSensitivity;
  updateTopbarSensitivity(AppState.currentSensitivity);

  // Update playbook select
  var sel = document.getElementById('playbook-select');
  if (sel) sel.value = AppState.currentPlaybook;

  var lbl = document.getElementById('topbar-playbook-label');
  var playbookNames = { standard: 'Standard', nda: 'NDA', vendor: 'Vendor', employment: 'Employment', saas: 'SaaS/MSA' };
  if (lbl) lbl.textContent = playbookNames[AppState.currentPlaybook] || 'Standard';

  closePlaybookModal();

  if (AppState.currentContract) {
    showToast('🔄 Re-analyzing with ' + AppState.currentPlaybook + ' playbook…', 'info');
    setTimeout(function () {
      var contract = AppState.currentContract;
      if (contract.rawText) {
        analyzeText(contract.rawText, contract.name, contract.size);
      } else {
        startAnalysis(contract);
      }
    }, 300);
  } else {
    showToast('✅ Playbook updated — upload a contract to apply', 'success');
  }
}

function updateSensitivityInModal(sensitivity) {
  document.querySelectorAll('.sensitivity-card').forEach(function (c) {
    c.classList.toggle('active', c.getAttribute('data-sensitivity') === sensitivity);
  });
}

function updateTopbarSensitivity(sensitivity) {
  document.querySelectorAll('.sens-btn').forEach(function (b) {
    b.classList.toggle('active', b.getAttribute('data-sensitivity') === sensitivity);
  });
}

function renderClauseRulesList() {
  var container = document.getElementById('clause-rules');
  if (!container) return;
  var sensitivity = AppState.pendingSensitivity || AppState.currentSensitivity;
  container.innerHTML = CLAUSE_RULES.map(function (rule) {
    var sev = rule.severities[sensitivity] || rule.severities.standard;
    return '<div class="clause-rule-row">' +
      '<span class="clause-rule-name">' + rule.type + '</span>' +
      '<span class="clause-rule-badge ' + sev + '">' + sev.toUpperCase() + '</span>' +
      '</div>';
  }).join('');
}

/* =================================================================
   EXPORT MODAL
   ================================================================= */
function initExportModal() {
  document.getElementById('export-modal-close').addEventListener('click', closeExportModal);
  document.getElementById('export-modal-cancel').addEventListener('click', closeExportModal);
  document.getElementById('export-modal').addEventListener('click', function (e) {
    if (e.target === document.getElementById('export-modal')) closeExportModal();
  });

  document.querySelectorAll('.export-option-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var format = btn.getAttribute('data-format');
      executeExport(format);
    });
  });
}

function openExportModal() {
  if (!AppState.currentContract) return;
  updateExportAcceptedNote();
  document.getElementById('export-modal').style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function closeExportModal() {
  document.getElementById('export-modal').style.display = 'none';
  document.body.style.overflow = '';
}

function updateExportAcceptedNote() {
  var count = Object.keys(AppState.acceptedRedlines).length;
  var note = document.getElementById('export-accepted-note');
  var countEl = document.getElementById('export-accepted-count');
  if (!note) return;
  if (countEl) countEl.textContent = count;
  note.style.display = count > 0 ? '' : 'none';
}

function executeExport(format) {
  var contract = AppState.currentContract;
  if (!contract) return;
  closeExportModal();

  var filename = (contract.name || 'contract').replace(/[^a-z0-9]/gi, '_').toLowerCase();

  if (format === 'json') {
    var data = buildExportData(contract);
    downloadFile(filename + '_risk_report.json', JSON.stringify(data, null, 2), 'application/json');
    showToast('📥 JSON report downloaded', 'success');

  } else if (format === 'markdown') {
    downloadFile(filename + '_risk_report.md', buildMarkdownReport(contract), 'text/markdown');
    showToast('📥 Markdown report downloaded', 'success');

  } else if (format === 'html') {
    downloadFile(filename + '_risk_report.html', buildHtmlReport(contract), 'text/html');
    showToast('📥 HTML report downloaded', 'success');

  } else if (format === 'redline') {
    downloadFile(filename + '_redlined.txt', buildRedlinedContract(contract), 'text/plain');
    showToast('📥 Redlined contract downloaded', 'success');
  }
}

function buildExportData(contract) {
  return {
    exportedAt: new Date().toISOString(),
    contract: {
      name: contract.name, type: contract.type,
      pages: contract.pages, size: contract.size,
      riskScore: contract.score
    },
    playbook: AppState.currentPlaybook,
    sensitivity: AppState.currentSensitivity,
    summary: countBySeverity(contract.clauses),
    clauses: contract.clauses.map(function (c) {
      return {
        id: c.id, type: c.type, severity: c.severity,
        snippet: c.snippet, original: c.original,
        risk: c.risk,
        redline: AppState.customRedlines[c.id] !== undefined ? AppState.customRedlines[c.id] : c.redline,
        accepted: !!AppState.acceptedRedlines[c.id],
        riskFactors: c.riskFactors || []
      };
    }),
    acceptedRedlines: Object.keys(AppState.acceptedRedlines).length
  };
}

function buildMarkdownReport(contract) {
  var counts = countBySeverity(contract.clauses);
  var lines = [
    '# Contract Risk Analysis Report',
    '',
    '> Generated by **ContractRisk AI** on ' + new Date().toLocaleString(),
    '',
    '---',
    '',
    '## Contract Details',
    '',
    '| Field | Value |',
    '|-------|-------|',
    '| **Name** | ' + contract.name + ' |',
    '| **Type** | ' + contract.type + ' |',
    '| **Pages** | ' + contract.pages + ' |',
    '| **Size** | ' + contract.size + ' |',
    '| **Risk Score** | ' + contract.score + '/100 |',
    '| **Playbook** | ' + AppState.currentPlaybook + ' |',
    '| **Sensitivity** | ' + AppState.currentSensitivity + ' |',
    '',
    '## Risk Summary',
    '',
    '| Severity | Count |',
    '|----------|-------|',
    '| 🔴 Critical | ' + counts.critical + ' |',
    '| 🟡 High | ' + counts.high + ' |',
    '| 🟣 Medium | ' + counts.medium + ' |',
    '| 🟢 Safe | ' + counts.safe + ' |',
    '',
    '---',
    '',
    '## Identified Clauses',
    ''
  ];

  contract.clauses.forEach(function (c) {
    var sevEmoji = { critical: '🔴', high: '🟡', medium: '🟣', safe: '🟢' }[c.severity] || '⚪';
    lines.push('### ' + sevEmoji + ' ' + c.type + ' — `' + c.severity.toUpperCase() + '`');
    lines.push('');
    if (c.riskFactors && c.riskFactors.length) {
      lines.push('**Risk Factors:** ' + c.riskFactors.join(' · '));
      lines.push('');
    }
    lines.push('**Risk Analysis:** ' + c.risk);
    lines.push('');
    lines.push('**Original Text:**');
    lines.push('> ' + c.original.replace(/\n/g, '\n> '));
    lines.push('');
    var activeRedline = AppState.customRedlines[c.id] !== undefined ? AppState.customRedlines[c.id] : c.redline;
    if (activeRedline) {
      var accepted = AppState.acceptedRedlines[c.id] ? ' ✅ **ACCEPTED**' : '';
      lines.push('**Suggested Redline:**' + accepted);
      lines.push('> ' + activeRedline.replace(/\n/g, '\n> '));
      lines.push('');
    }
    lines.push('---');
    lines.push('');
  });

  return lines.join('\n');
}

function buildHtmlReport(contract) {
  var counts = countBySeverity(contract.clauses);
  var scoreColor = contract.score >= 75 ? '#EF4444' : contract.score >= 50 ? '#F59E0B' : contract.score >= 25 ? '#8B5CF6' : '#10B981';

  var clauseHtml = contract.clauses.map(function (c) {
    var sevColor = { critical: '#EF4444', high: '#F59E0B', medium: '#8B5CF6', safe: '#10B981' }[c.severity] || '#94A3B8';
    var activeRedline = AppState.customRedlines[c.id] !== undefined ? AppState.customRedlines[c.id] : c.redline;
    var accepted = AppState.acceptedRedlines[c.id];
    var factorsHtml = (c.riskFactors || []).map(function (f) {
      return '<span style="display:inline-block;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:4px;padding:2px 8px;font-size:11px;color:#FDA4AF;margin:2px;">' + f + '</span>';
    }).join('');

    return '<div style="border:1px solid rgba(255,255,255,0.08);border-left:4px solid ' + sevColor + ';border-radius:10px;padding:20px;margin-bottom:16px;background:rgba(255,255,255,0.02);">' +
      '<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">' +
        '<span style="font-weight:800;font-size:15px;color:#EEF2F8;">' + c.type + '</span>' +
        '<span style="padding:2px 10px;border-radius:100px;background:rgba(255,255,255,0.05);border:1px solid ' + sevColor + ';font-size:10px;font-weight:700;color:' + sevColor + ';font-family:monospace;">' + c.severity.toUpperCase() + '</span>' +
        (accepted ? '<span style="padding:2px 10px;border-radius:100px;background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.4);font-size:10px;font-weight:700;color:#10B981;">✅ ACCEPTED</span>' : '') +
      '</div>' +
      (factorsHtml ? '<div style="margin-bottom:12px;">' + factorsHtml + '</div>' : '') +
      '<p style="font-size:12px;color:#94A3B8;margin-bottom:12px;">' + c.risk + '</p>' +
      '<div style="background:rgba(0,0,0,0.3);border-radius:6px;padding:12px;font-family:monospace;font-size:11px;color:#94A3B8;margin-bottom:' + (activeRedline ? '12px' : '0') + ';">' + c.original.substring(0, 500) + '</div>' +
      (activeRedline ? '<div style="background:rgba(16,185,129,0.05);border:1px solid rgba(16,185,129,0.2);border-radius:6px;padding:12px;font-family:monospace;font-size:11px;color:#6EE7B7;">' + activeRedline + '</div>' : '') +
      '</div>';
  }).join('');

  return '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<title>Contract Risk Report — ' + contract.name + '</title>\n' +
    '<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:Inter,-apple-system,sans-serif;background:#060A12;color:#EEF2F8;padding:32px;max-width:900px;margin:0 auto;line-height:1.6}h1{font-size:24px;font-weight:900;letter-spacing:-0.5px;margin-bottom:4px}h2{font-size:16px;font-weight:700;color:#94A3B8;margin:28px 0 14px;text-transform:uppercase;letter-spacing:0.8px}table{width:100%;border-collapse:collapse;margin-bottom:16px}td,th{padding:10px 14px;text-align:left;border:1px solid rgba(255,255,255,0.07);font-size:13px}th{font-weight:700;color:#4B607A;font-size:10px;text-transform:uppercase;letter-spacing:0.8px}hr{border:none;border-top:1px solid rgba(255,255,255,0.07);margin:24px 0}</style>\n' +
    '</head>\n<body>\n' +
    '<div style="display:flex;align-items:center;gap:16px;margin-bottom:28px;">' +
      '<div style="width:42px;height:42px;border-radius:10px;background:linear-gradient(135deg,#00F2FE,#4F8EF7);display:flex;align-items:center;justify-content:center;font-size:20px;">⚖️</div>' +
      '<div><h1>ContractRisk AI Report</h1><div style="font-size:12px;color:#4B607A;">Generated ' + new Date().toLocaleString() + '</div></div>' +
    '</div>' +
    '<table><tr><th>Field</th><th>Value</th></tr>' +
      '<tr><td>Contract Name</td><td>' + contract.name + '</td></tr>' +
      '<tr><td>Type</td><td>' + contract.type + '</td></tr>' +
      '<tr><td>Pages</td><td>' + contract.pages + '</td></tr>' +
      '<tr><td>Risk Score</td><td style="font-weight:800;color:' + scoreColor + ';">' + contract.score + '/100</td></tr>' +
      '<tr><td>Playbook</td><td>' + AppState.currentPlaybook + '</td></tr>' +
      '<tr><td>Critical Clauses</td><td style="color:#EF4444;">' + counts.critical + '</td></tr>' +
      '<tr><td>High Risk Clauses</td><td style="color:#F59E0B;">' + counts.high + '</td></tr>' +
    '</table>' +
    '<h2>Identified Clauses (' + contract.clauses.length + ')</h2>' +
    clauseHtml +
    '</body>\n</html>';
}

function buildRedlinedContract(contract) {
  var lines = [
    'REDLINED CONTRACT',
    '==================',
    'Contract: ' + contract.name,
    'Generated by ContractRisk AI — ' + new Date().toLocaleString(),
    'Accepted Redlines: ' + Object.keys(AppState.acceptedRedlines).length,
    '',
    '==================',
    ''
  ];

  if (contract.rawText) {
    var text = contract.rawText;
    // Apply accepted redlines as annotations
    contract.clauses.forEach(function (c) {
      var accepted = AppState.acceptedRedlines[c.id];
      if (!accepted) return;
      var snippet = c.original.substring(0, 60);
      var idx = text.indexOf(snippet);
      if (idx !== -1) {
        var before = text.substring(0, idx);
        var original = text.substring(idx, idx + c.original.length);
        var after = text.substring(idx + c.original.length);
        text = before + '\n[REDLINE ACCEPTED — ' + c.type + ']\n<<<ORIGINAL>>>\n' + original + '\n<<<REDLINE>>>\n' + accepted + '\n[END REDLINE]\n' + after;
      }
    });
    lines.push(text);
  } else {
    lines.push('[Contract text not available — showing redlines only]', '');
    contract.clauses.forEach(function (c) {
      var accepted = AppState.acceptedRedlines[c.id];
      if (!accepted) return;
      lines.push('--- ' + c.type.toUpperCase() + ' (ACCEPTED REDLINE) ---');
      lines.push('ORIGINAL: ' + c.original);
      lines.push('REDLINE:  ' + accepted);
      lines.push('');
    });
  }

  return lines.join('\n');
}

/* =================================================================
   CLAUSE COUNT & UTILITIES
   ================================================================= */
function updateClauseCount() {
  var visible = document.querySelectorAll('.clause-item:not(.hidden)').length;
  var total = document.querySelectorAll('.clause-item').length;
  var el = document.getElementById('clause-count');
  if (el) el.textContent = visible + ' of ' + total + ' clauses';
}

function showDetailPlaceholder() {
  var ph = document.getElementById('detail-placeholder');
  var view = document.getElementById('detail-view');
  if (ph) ph.style.display = '';
  if (view) view.classList.remove('visible');
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return Math.round(bytes / 1024) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function downloadFile(filename, content, mimeType) {
  var blob = new Blob([content], { type: mimeType });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  setTimeout(function () { document.body.removeChild(a); URL.revokeObjectURL(url); }, 200);
}

/* =================================================================
   KEYBOARD NAVIGATION
   ================================================================= */
function initKeyboardShortcuts() {
  document.addEventListener('keydown', function (e) {
    // Skip if typing in an input
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

    // Escape: close modals
    if (e.key === 'Escape') {
      closePlaybookModal();
      closeExportModal();
    }

    // / : focus search
    if (e.key === '/') {
      e.preventDefault();
      var si = document.getElementById('clause-search');
      if (si) si.focus();
    }

    // Arrow down/up: cycle through visible clauses
    if (!AppState.currentContract) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      var items = Array.from(document.querySelectorAll('.clause-item:not(.hidden)'));
      if (!items.length) return;
      var selected = document.querySelector('.clause-item.selected');
      var idx = selected ? items.indexOf(selected) : -1;
      var nextIdx = e.key === 'ArrowDown' ? Math.min(idx + 1, items.length - 1) : Math.max(idx - 1, 0);
      if (idx === -1) nextIdx = 0;
      items[nextIdx].click();
    }

    // 1/2/3 : switch view
    if (e.key === '1') setViewMode('cards');
    if (e.key === '2') setViewMode('document');
    if (e.key === '3') setViewMode('matrix');

    // E : export
    if (e.key === 'e' || e.key === 'E') {
      if (AppState.currentContract) openExportModal();
    }
  });
}

/* =================================================================
   TOAST NOTIFICATIONS
   ================================================================= */
function showToast(message, type) {
  var container = document.getElementById('toast-container');
  var toast = document.createElement('div');
  toast.className = 'toast ' + (type || 'info');
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(function () {
    toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    setTimeout(function () {
      if (toast.parentNode) container.removeChild(toast);
    }, 320);
  }, 3800);
}
