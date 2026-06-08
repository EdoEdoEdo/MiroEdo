'use client';

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useState,
    type ReactNode,
} from 'react';

export type Locale = 'it' | 'en';

type Dict = Record<string, string>;

const IT: Dict = {
    'nav.home': 'Home',
    'nav.new_report': 'Nuovo report',
    'nav.info': 'Info',
    'about.eyebrow': 'INFO · PROGETTO E AUTORE',
    'about.tagline':
        'Brand intelligence engine — ingestione universale, report editoriale, simulazione sociale OASIS e chat ReAct su un knowledge graph persistente.',
    'about.by': 'di',
    'about.s0.title': 'Origine',
    'about.s0.p1':
        'MiroEdo è una reimplementazione da zero di MiroFish — stesso dominio (social listening + simulazione ad agenti), stack moderno: FastAPI + Pydantic, Next.js 15, multi-provider LLM (Mistral / Groq / OpenAI), Zep opzionale, type safety end-to-end.',
    'about.s0.p2':
        "La build pubblicata qui è una vetrina statica con dati mock, per far navigare l'esperienza senza credenziali né backend acceso. Lo stesso codice gira end-to-end sui free tier Mistral + Groq (Llama 70B) a costo zero, o su GPT-4/Claude/Mistral Large se preferisci: il provider è una scelta runtime.",
    'about.s0.flow_title': 'Differenze di flusso vs MiroFish',
    'about.s0.col_axis': 'Aspetto',
    'about.s0.col_mf': 'MiroFish',
    'about.s0.col_me': 'MiroEdo',
    'about.s0.row1_label': 'Input',
    'about.s0.row1_mf':
        'Crawler MindSpider proprietario su Weibo / Zhihu (mercato cinese).',
    'about.s0.row1_me':
        'Adapter universale CSV / XLSX / PDF / MD → schema BrandSeed (Pydantic).',
    'about.s0.row2_label': 'Pipeline',
    'about.s0.row2_mf':
        'Step-driven, dipendente da Knowledge Graph Zep persistente.',
    'about.s0.row2_me':
        "Mode-driven (quick / full), Zep opzionale, calcoli deterministici separati dall'LLM.",
    'about.s0.row3_label': 'Output',
    'about.s0.row3_mf': 'Report markdown grezzo dal motore.',
    'about.s0.row3_me':
        'Report editoriale + Executive Summary + KPI + Action Plan 72h (postprocess dedicato).',
    'about.s0.row4_label': 'Delivery',
    'about.s0.row4_mf': 'Monolitico: frontend Vue servito dal backend Flask.',
    'about.s0.row4_me':
        'Disaccoppiato: export statico Next.js (CDN-friendly) + FastAPI deployabile separatamente.',
    'about.s1.title': 'Il problema',
    'about.s1.p1':
        'I tool di social listening ti danno dashboard. Le dashboard ti dicono \"cosa\" è successo, ma raramente \"perché\" e mai \"cosa fare adesso\". Per arrivare a una decisione un brand manager passa giorni a copia-incollare numeri in slide.',
    'about.s1.p2':
        "MiroEdo prende un export grezzo (CSV/XLSX/PDF/MD) e in pochi minuti restituisce un documento di brand intelligence ad alta densità narrativa con KPI, driver, scenari prospettici, piano d'azione 72h e una chat che sa rispondere combinando report, knowledge graph, dataset e personas simulate.",
    'about.s1.li1':
        'Ingestione universale — niente schemi proprietari, prendi quello che ti dà il vendor.',
    'about.s1.li2':
        'Output editoriale — markdown leggibile, non \"dashboard intercambiabili\".',
    'about.s1.li3': 'Simulazione sociale — testa scenari prima di pubblicare.',
    'about.s2.title': 'Il metodo',
    'about.s2.p1':
        "Pipeline a 5 stadi. Ogni stadio è indipendente, testabile e produce un artefatto strutturato (Pydantic). L'LLM viene usato come strumento dove serve (estrazione ontologia, redazione narrativa, ragionamento multi-hop nella chat) ma non sostituisce mai i calcoli deterministici (KPI, forecast, scoring).",
    'about.s3.title': "Cosa c'è dentro",
    'about.s3.p1': 'Cinque motori indipendenti, orchestrati dal pipeline.',
    'about.s3.e1':
        'Adapter universale CSV/XLSX/PDF/MD → schema canonico BrandSeed.',
    'about.s3.e2':
        'Estrae KPI deterministici, driver osservati e scenari prospettici dal seed.',
    'about.s3.e3':
        'Forecast volume mention (Holt-Winters), ontologia stakeholder AI-inferred.',
    'about.s3.e4':
        'Genera 40 personas (configurabile) e fa simulare reazioni LLM-driven su OASIS (camel-ai). Tre patch custom al runner upstream (max_iteration=5, no DO_NOTHING, bootstrap engagement) per ottenere conversazioni vive invece di refresh/do_nothing.',
    'about.s3.e5':
        'Compone il report finale e ospita la chat ReAct con 6 tool su Zep + dataset + personas.',
    'about.s4.title': 'Stack tecnico',
    'about.s5.title': 'Il flow demo',
    'about.s5.intro':
        'Due showcase precaricati come demo statiche: NordaLatte (crisis-recall latticini, brief PDF) e Verdaia (lancio ESG FMCG, 50 mention CSV). Sono cliccabili dalla home senza backend.',
    'about.s5.f1t': 'Upload',
    'about.s5.f1d':
        'Trascini un file. Schema autodetect. Anteprima righe/colonne.',
    'about.s5.f2t': 'Setup',
    'about.s5.f2d':
        'Confermi brand, lingua, mode (fast/full) e la domanda di business.',
    'about.s5.f3t': 'Simulation',
    'about.s5.f3d':
        'Genera personas, lancia OASIS, vedi knowledge graph + stream live.',
    'about.s5.f4t': 'Report',
    'about.s5.f4d':
        'Markdown editoriale con KPI, driver, scenari, forecast, heatmap, piano 72h.',
    'about.s5.f5t': 'Interaction',
    'about.s5.f5d':
        'Chat sul report. Toggle AGENT per ragionamento multi-hop con tool.',
    'about.s6.title': 'Autore',
    'about.s6.p1':
        "Sono Edoardo Di Sabatino, frontend developer con la passione per l'AI. Mi diverto a sperimentare 3D e intelligenza artificiale sul web — e MiroEdo nasce esattamente da questa frizione fra interfacce, dati e modelli. Sul mio sito personale trovi gli altri esperimenti.",
    'about.s6.site_label': 'SITO PERSONALE',
    'about.s6.gh_label': 'CODICE',
    'about.s6.other_projects': 'ALTRI PROGETTI',
    'about.s6.deepscroll':
        'documentari storici generati da LLM + Guardian API in formato scrollytelling.',
    'about.s6.more': 'esperimenti AI, tool, repo open source.',
    'about.cta_try': 'Prova la demo',
    'upload.sample_label': 'Non hai un dataset?',
    'upload.sample_meta':
        '50 mention · 14 colonne · schema social-listening compatible',
    'upload.sample_meta_nordalatte':
        '4 settimane · brief crisis-recall · 1.247 mention',
    'upload.example_picker_label': 'SCEGLI UN ESEMPIO PRECONFEZIONATO',
    'upload.example_verdaia_tag': 'CSV · ESG LAUNCH',
    'upload.example_verdaia_title': 'Verdaia Foods — lancio politica ESG',
    'upload.example_verdaia_desc':
        '8.742 mention su 14 giorni. Sentiment +0.18. Driver: tracciabilità, prezzo premium, greenwashing.',
    'upload.example_nordalatte_tag': 'PDF · CRISIS-RECALL',
    'upload.example_nordalatte_title':
        'NordaLatte — richiamo Listeria CremaPiù',
    'upload.example_nordalatte_desc':
        '1.247 mention su 22 giorni. Sentiment −0.12. Driver: fiducia famiglie, timing comunicazione, trasparenza ATS.',
    'home.eyebrow': 'BRAND INTELLIGENCE ENGINE',
    'home.sub':
        "Carica un qualsiasi export di social listening (CSV, XLSX) o un brief (PDF, MD, TXT), ottieni un report editoriale italiano con KPI, simulazione OASIS e piano d'azione 72h.",
    'home.cta_new': 'Nuovo report',
    'home.cta_recent': 'Vedi cronologia',
    'home.pills.csv': 'CSV / XLSX / PDF',
    'home.pills.oasis': 'OASIS sim',
    'home.pills.mistral': 'Mistral',
    'home.pills.ita': 'Italiano',
    'history.title': 'Report recenti',
    'history.count': 'TOTALE',
    'history.empty':
        'Nessun report ancora. Avvia il primo da \u201CNuovo report\u201D.',
    'history.loading': 'Carico la cronologia\u2026',
    'history.error': 'Errore caricamento cronologia: ',
    'status.queued': 'IN CODA',
    'status.running': 'IN CORSO',
    'status.succeeded': 'COMPLETATO',
    'status.failed': 'FALLITO',
    'wizard.step1': 'Upload',
    'wizard.step2': 'Setup',
    'wizard.step3': 'Simulazione',
    'wizard.step4': 'Report',
    'wizard.step5': 'Interazione',
    'upload.title': 'Carica i dati',
    'upload.sub':
        'Trascina un file (CSV, XLSX, PDF, MD, TXT) oppure clicca per selezionarlo.',
    'upload.dropzone_label': 'QUALSIASI FILE (CSV/XLSX/PDF/MD/TXT)',
    'upload.dropzone_title': 'TRASCINA IL FILE QUI',
    'upload.dropzone_hint': 'oppure clicca per selezionarlo — max 50MB',
    'upload.brand_label': 'BRAND',
    'upload.brand_hint': 'Nome ufficiale del brand da analizzare',
    'upload.brand_placeholder': 'Nome del brand',
    'upload.mode_label': 'MODALIT\u00C0',
    'upload.mode_quick': 'Quick (no simulazione)',
    'upload.mode_full': 'Full (con OASIS)',
    'upload.sim_label': 'Simulazione OASIS',
    'upload.scenario_label': 'SCENARIO DI BUSINESS (opzionale)',
    'upload.scenario_placeholder':
        'Descrivi la domanda strategica a cui vuoi rispondere. Esempio:\n\nVerdaia Foods sta valutando contromisure per ridurre il churn nel Q3-Q4 2026 dopo un rincaro listino del +4% sui prodotti tracciati ESG. Analizza reazione clienti storici, intent di switch verso competitor, ruolo dei comparatori, sentiment per segmento, eventuali crisi reputazionali. Produci predizioni quantitative, action plan 72h e 3 scenari (best/base/worst).',
    'upload.scenario_hint':
        'Inquadra la lettura del report e guida executive summary, action plan e chat',
    'upload.submit': 'Avvia analisi',
    'upload.submitting': 'Avvio in corso…',
    'upload.error': 'Errore: ',
    'upload.missing_file': 'Seleziona un file prima di continuare.',
    'upload.missing_brand': 'Inserisci il nome del brand.',
    'process.title': 'Processo',
    'process.eyebrow': 'RUN',
    'process.step_now': 'STEP ATTUALE',
    'process.go_report': 'Apri report',
    'process.go_sim': 'Vai alla simulazione',
    'process.go_interaction': "Vai all'interazione",
    'process.warnings': 'Avvisi',
    'process.loading': 'Carico stato\u2026',
    'sim.title': 'Simulazione OASIS',
    'sim.sub': 'Configura e avvia una simulazione di pubblico sintetico.',
    'sim.start': 'Avvia simulazione',
    'sim.stub':
        'Per ora la simulazione viene eseguita automaticamente quando la run \u00E8 in modalit\u00E0 Full. Riavvii indipendenti arriveranno in M5.',
    'sim.back': 'Torna al processo',
    'sim.run_title': 'Esecuzione live',
    'sim.run_status': 'Stato',
    'sim.run_log': 'Log progresso',
    'report.title': 'Report',
    'report.kpi_label': 'KPI',
    'report.actions_label': "PIANO D'AZIONE 72H",
    'report.summary_label': 'EXECUTIVE SUMMARY',
    'report.warnings': 'Avvisi',
    'report.empty':
        'Report non disponibile. La run potrebbe non essere completata.',
    'report.kpi.chapters': 'CAPITOLI',
    'report.kpi.words': 'PAROLE',
    'report.kpi.density': 'DENSIT\u00C0 NUM.',
    'report.kpi.predictions': 'PREDIZIONI',
    'report.kpi.simulation': 'AZIONI SIM',
    'report.kpi.profiles': 'PROFILI SIM',
    'report.no_simulation': 'Simulazione non eseguita in questa run.',
    'report.download_md': 'Scarica markdown',
    'report.download_pdf': 'Scarica PDF',
    'interaction.title': 'Interazione',
    'interaction.stub_title': 'PROSSIMAMENTE',
    'interaction.stub_sub':
        "La chat di interrogazione del report \u00E8 nella roadmap. Per ora puoi consultare il report e il piano d'azione.",
    'interaction.eyebrow': 'CHAT · GROUNDED ON REPORT',
    'interaction.empty_title': 'Chiedi al report',
    'interaction.empty_sub':
        "Domande in italiano sui dati di brand, sentiment, segmenti, simulazione OASIS o piano d'azione.",
    'interaction.you': 'TU',
    'interaction.thinking': 'sto leggendo il report…',
    'interaction.send': 'Invia',
    'interaction.placeholder':
        'Scrivi una domanda… (Invio per inviare, Shift+Invio per nuova riga)',
    'interaction.sug.sentiment': 'Qual è il sentiment medio?',
    'interaction.sug.topic': 'Qual è il topic più critico?',
    'interaction.sug.actions': 'Riassumi le prime 3 azioni del piano 72h',
    'interaction.sug.sim': 'Cosa ci dice la simulazione OASIS?',
    'interaction.sources': 'FONTI',
    'interaction.confidence': 'Livello di confidenza della risposta',
    'interaction.out_of_scope':
        'Dato non presente nel report: la risposta non è verificabile sulle fonti disponibili.',
    'common.brand': 'Brand',
    'common.mode': 'Modalit\u00E0',
    'common.created': 'Creato',
    'common.updated': 'Aggiornato',
    'common.source': 'Sorgente',
    'common.back_home': 'Torna alla home',
    'common.run_id': 'RUN ID',
    'upload.demo_banner_label': 'DEMO STATICA',
    'upload.demo_banner_intro': 'i campi sono pre-compilati e bloccati. Premi',
    'upload.demo_banner_outro': 'per visualizzare il run gi\u00E0 elaborato.',
    'upload.attached_file': 'FILE ALLEGATO',
    'upload.attached_meta':
        '184 KB \u00B7 CSV \u00B7 8.742 mention \u00B7 2026-Q1',
    'upload.llm_label': 'Modello report',
    'upload.llm_missing_key': '(API key mancante)',
    'upload.llm_hint_default':
        'Provider OpenAI-compatible. Usato per ingestion e redazione del report. La simulazione ha un suo selettore dedicato.',
    'upload.sim_hint':
        'La simulazione OASIS si lancia dopo il report dalla pagina dedicata, scegliendo numero di agenti e round.',
    'upload.mode_full_hint': '+OASIS +LLM (Mistral)',
    'upload.mode_quick_hint': 'no LLM sim',
    'chat.footnote.mode_agent':
        'Multi-hop \u00B7 accede a Zep, dataset, personas, metriche',
    'chat.footnote.mode_rag': 'Risposta in streaming sulle sezioni del report',
    'chat.footnote.cta': "cos'\u00E8?",
    'chat.footnote.rag_default': '(default)',
    'chat.footnote.rag_body':
        'Retrieval sulle sezioni del report gi\u00E0 generato \u2192 un singolo passaggio LLM \u2192 risposta in streaming token-per-token con citazioni alle sezioni. Veloce, deterministico, costo basso. Ideale per domande di lettura/sintesi sul report.',
    'chat.footnote.agent_body':
        "L'LLM entra in un loop Reason \u2192 Act \u2192 Observe con 6 tool. Risponde a domande multi-hop combinando report + knowledge graph + CSV + personas. Pi\u00F9 lento e non-streaming, ma ragiona.",
    'live.personas_count': 'Agenti generati',
    'live.personas_empty':
        'Personas non ancora disponibili. Verranno mostrate qui appena il runner OASIS le genera.',
    'live.kg_title': 'Knowledge graph live',
    'live.stream_title': 'Stream azioni live',
    'live.counter_round': 'round',
    'live.counter_actions': 'azioni',
    'live.counter_active': 'attivi',
    'live.timeline_title': 'Timeline azioni',
    'live.timeline_meta_suffix': 'bucket',
    'live.timeline_actions_suffix': 'azioni',
    'live.terminal_waiting': 'in attesa del primo step OASIS\u2026',
    'live.terminal_idle': 'avvia la simulazione per popolare lo stream.',
    'live.terminal_no_actions': 'nessuna azione registrata.',
    'live.zep_title': 'Knowledge graph emergente (Zep)',
    'live.zep_status_idle': 'in attesa',
    'live.zep_status_prefix': 'STATUS',
    'live.zep_empty':
        'Il grafo Zep verr\u00E0 disegnato qui non appena la simulazione raggiunge lo step di enrichment.',
    'live.zep_metric_graph': 'GRAFO',
    'live.zep_metric_facts': 'FACT REGISTRATI',
    'live.zep_metric_nodes': 'NODI / EDGE',
    'live.zep_persisted':
        'Memoria semantica salvata su Zep: brand, topic, segmenti, sentiment e piattaforme sono registrati come fact interrogabili.',
    'live.zep_preview':
        'Preview locale del grafo che verrebbe registrato. Configura ZEP_API_KEY per persisterlo.',
    'live.zep_waiting': 'In attesa dei dati di enrichment.',
    'kg.no_nodes': 'Nessun nodo visibile con i filtri correnti.',
    'kg.stats_suffix': 'trascina per spostare, scrolla per zoom.',
    'kg.stats_nodes': 'nodi',
    'kg.stats_edges': 'relazioni',
    'ontology.model_label': 'modello \u00B7',
    'samples.subtitle':
        'Estratti dalla simulazione OASIS, ordinati per influenza prevista (combinazione di reach, hot topics e polarizzazione).',
    'zepqa.subtitle':
        'Domande pre-generate, risposte basate sui fact registrati nel grafo Zep durante la simulazione.',
    'sim.base_not_ready':
        'Il report base non \u00E8 ancora pronto. Torna alla pagina di processo e attendi il completamento.',
    'sim.config_title': 'CONFIGURA SIMULAZIONE OASIS',
    'sim.field_agents': 'AGENTI SINTETICI',
    'sim.field_agents_hint': '3\u2013120 personas. Default 40.',
    'sim.field_rounds': 'ROUND OASIS',
    'sim.field_model': 'MODELLO SIMULAZIONE',
    'sim.field_model_hint':
        'Usato per le reazioni LLM degli agenti durante la simulazione.',
    'sim.field_model_hint_static':
        'Demo statica: output precalcolato, modello bloccato su GPT-4o.',
    'sim.eyebrow_step': 'STEP 03 \u00B7 OASIS',
    'sim.report_unlocks':
        'Report e interazione si sbloccano dopo la simulazione.',
    'report.locked_title': 'Report non ancora sbloccato',
    'report.locked_body':
        'Il report finale si apre dopo la simulazione OASIS. Il report base \u00E8 gi\u00E0 pronto, ma manca lo step 3.',
    'report.go_sim_cta': 'VAI ALLA SIMULAZIONE \u2192',
    'sim.field_rounds_hint': '1\u201310 round interazione. Default 4.',
    'sim.starting': 'AVVIO\u2026',
    'sim.launch_cta': 'AVVIA SIMULAZIONE \u2192',
    'sim.open_report_cta': 'APRI REPORT \u2192',
    'sim.retry': 'RIPROVA',
    'sim.failed_label': 'SIMULAZIONE FALLITA',
    'sim.unknown_error': 'Errore sconosciuto',
    'sim.kpi_profiles': 'PROFILI',
    'sim.kpi_actions': 'AZIONI',
    'sim.kpi_zep': 'ZEP',
};

const EN: Dict = {
    'nav.home': 'Home',
    'nav.new_report': 'New report',
    'nav.info': 'About',
    'about.eyebrow': 'ABOUT · PROJECT & AUTHOR',
    'about.tagline':
        'Brand intelligence engine — universal ingestion, editorial report, OASIS social simulation and a ReAct chat over a persistent knowledge graph.',
    'about.by': 'by',
    'about.s0.title': 'Origin',
    'about.s0.p1':
        'MiroEdo is a ground-up reimplementation of MiroFish — same problem space (social listening + agent-based simulation), modern stack: FastAPI + Pydantic, Next.js 15, multi-provider LLM (Mistral / Groq / OpenAI), optional Zep, end-to-end type safety.',
    'about.s0.p2':
        'The build published here is a static showcase with mock data, so the experience can be navigated without credentials or a running backend. The same codebase runs end-to-end on the Mistral + Groq free tiers (Llama 70B) at zero cost, or on GPT-4 / Claude / Mistral Large if you prefer: the provider is a runtime choice.',
    'about.s0.flow_title': 'Flow differences vs MiroFish',
    'about.s0.col_axis': 'Aspect',
    'about.s0.col_mf': 'MiroFish',
    'about.s0.col_me': 'MiroEdo',
    'about.s0.row1_label': 'Input',
    'about.s0.row1_mf':
        'Proprietary MindSpider crawler on Weibo / Zhihu (Chinese market).',
    'about.s0.row1_me':
        'Universal adapter CSV / XLSX / PDF / MD → BrandSeed schema (Pydantic).',
    'about.s0.row2_label': 'Pipeline',
    'about.s0.row2_mf':
        'Step-driven, depends on a persistent Zep Knowledge Graph.',
    'about.s0.row2_me':
        'Mode-driven (quick / full), Zep optional, deterministic computation kept separate from the LLM.',
    'about.s0.row3_label': 'Output',
    'about.s0.row3_mf': 'Raw markdown report from the engine.',
    'about.s0.row3_me':
        'Editorial report + Executive Summary + KPIs + 72h Action Plan (dedicated postprocess).',
    'about.s0.row4_label': 'Delivery',
    'about.s0.row4_mf': 'Monolithic: Vue frontend served by the Flask backend.',
    'about.s0.row4_me':
        'Decoupled: Next.js static export (CDN-friendly) + FastAPI deployable separately.',
    'about.s1.title': 'The problem',
    'about.s1.p1':
        'Social listening tools give you dashboards. Dashboards tell you \"what\" happened, rarely \"why\", and never \"what to do next\". To get to a decision, a brand manager spends days copy-pasting numbers into slides.',
    'about.s1.p2':
        'MiroEdo takes a raw export (CSV/XLSX/PDF/MD) and in minutes returns a high-density brand intelligence document with KPIs, drivers, prospective scenarios, a 72h action plan and a chat that can answer by combining report, knowledge graph, dataset and simulated personas.',
    'about.s1.li1':
        'Universal ingestion — no proprietary schemas, you bring what the vendor exports.',
    'about.s1.li2':
        'Editorial output — readable markdown, not \"interchangeable dashboards\".',
    'about.s1.li3': 'Social simulation — test scenarios before you publish.',
    'about.s2.title': 'The method',
    'about.s2.p1':
        'Five-stage pipeline. Each stage is independent, testable and produces a structured artifact (Pydantic). The LLM is used as a tool where it matters (ontology extraction, narrative writing, multi-hop chat reasoning) but never replaces deterministic computation (KPIs, forecasts, scoring).',
    'about.s3.title': "What's inside",
    'about.s3.p1': 'Five independent engines, orchestrated by the pipeline.',
    'about.s3.e1':
        'Universal adapter CSV/XLSX/PDF/MD → canonical BrandSeed schema.',
    'about.s3.e2':
        'Extracts deterministic KPIs, observed drivers and prospective scenarios from the seed.',
    'about.s3.e3':
        'Mention volume forecast (Holt-Winters), AI-inferred stakeholder ontology.',
    'about.s3.e4':
        'Generates 40 personas (configurable) and runs LLM-driven reactions on OASIS (camel-ai). Three custom patches over upstream (max_iteration=5, no DO_NOTHING, bootstrap engagement) to get lively conversations instead of refresh/do_nothing.',
    'about.s3.e5':
        'Composes the final report and hosts the ReAct chat with 6 tools over Zep + dataset + personas.',
    'about.s4.title': 'Tech stack',
    'about.s5.title': 'The demo flow',
    'about.s5.intro':
        'Two pre-loaded static demos: NordaLatte (dairy crisis-recall, PDF brief) and Verdaia (FMCG ESG launch, 50-mention CSV). Both clickable from the home with no backend.',
    'about.s5.f1t': 'Upload',
    'about.s5.f1d': 'Drop a file. Auto-detected schema. Row/column preview.',
    'about.s5.f2t': 'Setup',
    'about.s5.f2d':
        'Confirm brand, language, mode (fast/full) and the business question.',
    'about.s5.f3t': 'Simulation',
    'about.s5.f3d':
        'Generates personas, runs OASIS, see the knowledge graph + live stream.',
    'about.s5.f4t': 'Report',
    'about.s5.f4d':
        'Editorial markdown with KPIs, drivers, scenarios, forecast, heatmap, 72h plan.',
    'about.s5.f5t': 'Interaction',
    'about.s5.f5d':
        'Chat on the report. Toggle AGENT for multi-hop reasoning with tools.',
    'about.s6.title': 'Author',
    'about.s6.p1':
        "I'm Edoardo Di Sabatino, a frontend developer with a passion for AI. I have fun experimenting with 3D and artificial intelligence on the web — and MiroEdo is born exactly from that friction between interfaces, data and models. The rest of the experiments live on my personal site.",
    'about.s6.site_label': 'PERSONAL SITE',
    'about.s6.gh_label': 'CODE',
    'about.s6.other_projects': 'OTHER PROJECTS',
    'about.s6.deepscroll':
        'historical documentaries generated by LLM + Guardian API in scrollytelling format.',
    'about.s6.more': 'AI experiments, tools, open source repos.',
    'about.cta_try': 'Try the demo',
    'upload.sample_label': 'No dataset on hand?',
    'upload.sample_meta':
        '50 mentions · 14 columns · social-listening compatible schema',
    'upload.sample_meta_nordalatte':
        '4 weeks · crisis-recall brief · 1,247 mentions',
    'upload.example_picker_label': 'PICK A PRE-BUILT EXAMPLE',
    'upload.example_verdaia_tag': 'CSV · ESG LAUNCH',
    'upload.example_verdaia_title': 'Verdaia Foods — ESG policy launch',
    'upload.example_verdaia_desc':
        '8,742 mentions over 14 days. Sentiment +0.18. Drivers: traceability, premium price, greenwashing.',
    'upload.example_nordalatte_tag': 'PDF · CRISIS-RECALL',
    'upload.example_nordalatte_title': 'NordaLatte — CremaPiù Listeria recall',
    'upload.example_nordalatte_desc':
        '1,247 mentions over 22 days. Sentiment −0.12. Drivers: family trust, communication timing, ATS transparency.',
    'home.eyebrow': 'BRAND INTELLIGENCE ENGINE',
    'home.sub':
        'Upload any social-listening export (CSV, XLSX) or a brief (PDF, MD, TXT), get an editorial Italian report with KPIs, OASIS simulation and 72h action plan.',
    'home.cta_new': 'New report',
    'home.cta_recent': 'View history',
    'home.pills.csv': 'CSV / XLSX / PDF',
    'home.pills.oasis': 'OASIS sim',
    'home.pills.mistral': 'Mistral',
    'home.pills.ita': 'Italian',
    'history.title': 'Recent reports',
    'history.count': 'TOTAL',
    'history.empty':
        'No report yet. Start the first from \u201CNew report\u201D.',
    'history.loading': 'Loading history\u2026',
    'history.error': 'History load error: ',
    'status.queued': 'QUEUED',
    'status.running': 'RUNNING',
    'status.succeeded': 'SUCCEEDED',
    'status.failed': 'FAILED',
    'wizard.step1': 'Upload',
    'wizard.step2': 'Setup',
    'wizard.step3': 'Simulation',
    'wizard.step4': 'Report',
    'wizard.step5': 'Interaction',
    'upload.title': 'Upload data',
    'upload.sub':
        'Drop a file (CSV, XLSX, PDF, MD, TXT) or click to select it.',
    'upload.dropzone_label': 'ANY FILE (CSV/XLSX/PDF/MD/TXT)',
    'upload.dropzone_title': 'DROP FILE HERE',
    'upload.dropzone_hint': 'or click to pick one — max 50MB',
    'upload.brand_label': 'BRAND',
    'upload.brand_hint': 'Official name of the brand to analyse',
    'upload.brand_placeholder': 'Brand name',
    'upload.mode_label': 'MODE',
    'upload.mode_quick': 'Quick (no simulation)',
    'upload.mode_full': 'Full (with OASIS)',
    'upload.sim_label': 'OASIS simulation',
    'upload.scenario_label': 'BUSINESS SCENARIO (optional)',
    'upload.scenario_placeholder':
        'Describe the strategic question you want answered. Example:\n\nVerdaia Foods is evaluating countermeasures to reduce Q3-Q4 2026 churn after a +4% list-price hike on ESG-traced products. Analyze loyal-customer reaction, switch intent toward competitors, role of comparators, sentiment by segment, possible reputational crises. Deliver quantitative predictions, a 72h action plan and 3 scenarios (best/base/worst).',
    'upload.scenario_hint':
        'Frames the report and steers executive summary, action plan and chat',
    'upload.submit': 'Start analysis',
    'upload.submitting': 'Starting…',
    'upload.error': 'Error: ',
    'upload.missing_file': 'Select a file before continuing.',
    'upload.missing_brand': 'Enter the brand name.',
    'process.title': 'Process',
    'process.eyebrow': 'RUN',
    'process.step_now': 'CURRENT STEP',
    'process.go_report': 'Open report',
    'process.go_sim': 'Go to simulation',
    'process.go_interaction': 'Go to interaction',
    'process.warnings': 'Warnings',
    'process.loading': 'Loading status\u2026',
    'sim.title': 'OASIS simulation',
    'sim.sub': 'Configure and launch a synthetic audience run.',
    'sim.start': 'Start simulation',
    'sim.stub':
        'For now the simulation runs automatically when the run is in Full mode. Independent re-runs land in M5.',
    'sim.back': 'Back to process',
    'sim.run_title': 'Live execution',
    'sim.run_status': 'Status',
    'sim.run_log': 'Progress log',
    'report.title': 'Report',
    'report.kpi_label': 'KPIs',
    'report.actions_label': '72H ACTION PLAN',
    'report.summary_label': 'EXECUTIVE SUMMARY',
    'report.warnings': 'Warnings',
    'report.empty': 'Report not available. The run may not be completed.',
    'report.kpi.chapters': 'CHAPTERS',
    'report.kpi.words': 'WORDS',
    'report.kpi.density': 'NUM. DENSITY',
    'report.kpi.predictions': 'PREDICTIONS',
    'report.kpi.simulation': 'SIM ACTIONS',
    'report.kpi.profiles': 'SIM PROFILES',
    'report.no_simulation': 'No simulation in this run.',
    'report.download_md': 'Download markdown',
    'report.download_pdf': 'Download PDF',
    'interaction.title': 'Interaction',
    'interaction.stub_title': 'COMING SOON',
    'interaction.stub_sub':
        'Report interrogation chat is on the roadmap. For now you can browse the report and action plan.',
    'interaction.eyebrow': 'CHAT · GROUNDED ON REPORT',
    'interaction.empty_title': 'Ask the report',
    'interaction.empty_sub':
        'Italian or English questions about brand data, sentiment, segments, OASIS simulation or action plan.',
    'interaction.you': 'YOU',
    'interaction.thinking': 'reading the report…',
    'interaction.send': 'Send',
    'interaction.placeholder':
        'Type a question… (Enter to send, Shift+Enter newline)',
    'interaction.sug.sentiment': 'What is the average sentiment?',
    'interaction.sug.topic': 'Which topic is most critical?',
    'interaction.sug.actions': 'Summarise the top 3 actions in the 72h plan',
    'interaction.sug.sim': 'What does the OASIS simulation tell us?',
    'interaction.sources': 'SOURCES',
    'interaction.confidence': 'Answer confidence level',
    'interaction.out_of_scope':
        'Data not in the report: this answer cannot be verified against the available sources.',
    'common.brand': 'Brand',
    'common.mode': 'Mode',
    'common.created': 'Created',
    'common.updated': 'Updated',
    'common.source': 'Source',
    'common.back_home': 'Back home',
    'common.run_id': 'RUN ID',
    'upload.demo_banner_label': 'STATIC DEMO',
    'upload.demo_banner_intro': 'fields are pre-filled and locked. Click',
    'upload.demo_banner_outro': 'to view the already processed run.',
    'upload.attached_file': 'ATTACHED FILE',
    'upload.attached_meta':
        '184 KB \u00B7 CSV \u00B7 8,742 mentions \u00B7 2026-Q1',
    'upload.llm_label': 'Report model',
    'upload.llm_missing_key': '(API key missing)',
    'upload.llm_hint_default':
        'OpenAI-compatible provider. Used for ingestion and report writing. The simulation has its own dedicated selector.',
    'upload.sim_hint':
        'OASIS simulation is launched after the report from its dedicated page, by choosing number of agents and rounds.',
    'upload.mode_full_hint': '+OASIS +LLM (Mistral)',
    'upload.mode_quick_hint': 'no LLM sim',
    'chat.footnote.mode_agent':
        'Multi-hop \u00B7 accesses Zep, dataset, personas, metrics',
    'chat.footnote.mode_rag': 'Streaming answer over the report sections',
    'chat.footnote.cta': 'what is it?',
    'chat.footnote.rag_default': '(default)',
    'chat.footnote.rag_body':
        'Retrieval over the already generated report sections \u2192 a single LLM pass \u2192 streaming answer token-by-token with citations to the sections. Fast, deterministic, low-cost. Ideal for reading/summary questions on the report.',
    'chat.footnote.agent_body':
        'The LLM enters a Reason \u2192 Act \u2192 Observe loop with 6 tools. Answers multi-hop questions by combining report + knowledge graph + CSV + personas. Slower and non-streaming, but it reasons.',
    'live.personas_count': 'Generated agents',
    'live.personas_empty':
        'Personas not yet available. They will appear here as soon as the OASIS runner generates them.',
    'live.kg_title': 'Live knowledge graph',
    'live.stream_title': 'Live action stream',
    'live.counter_round': 'round',
    'live.counter_actions': 'actions',
    'live.counter_active': 'active',
    'live.timeline_title': 'Action timeline',
    'live.timeline_meta_suffix': 'buckets',
    'live.timeline_actions_suffix': 'actions',
    'live.terminal_waiting': 'waiting for the first OASIS step\u2026',
    'live.terminal_idle': 'launch the simulation to populate the stream.',
    'live.terminal_no_actions': 'no action recorded.',
    'live.zep_title': 'Emerging knowledge graph (Zep)',
    'live.zep_status_idle': 'idle',
    'live.zep_status_prefix': 'STATUS',
    'live.zep_empty':
        'The Zep graph will be drawn here as soon as the simulation reaches the enrichment step.',
    'live.zep_metric_graph': 'GRAPH',
    'live.zep_metric_facts': 'FACTS REGISTERED',
    'live.zep_metric_nodes': 'NODES / EDGES',
    'live.zep_persisted':
        'Semantic memory saved on Zep: brand, topic, segments, sentiment and platforms are registered as queryable facts.',
    'live.zep_preview':
        'Local preview of the graph that would be registered. Configure ZEP_API_KEY to persist it.',
    'live.zep_waiting': 'Waiting for enrichment data.',
    'kg.no_nodes': 'No node visible with current filters.',
    'kg.stats_suffix': 'drag to move, scroll to zoom.',
    'kg.stats_nodes': 'nodes',
    'kg.stats_edges': 'edges',
    'ontology.model_label': 'model \u00B7',
    'samples.subtitle':
        'Extracted from the OASIS simulation, ordered by predicted influence (a combination of reach, hot topics and polarization).',
    'zepqa.subtitle':
        'Pre-generated questions, answers grounded on facts registered in the Zep graph during the simulation.',
    'sim.base_not_ready':
        'Base report is not ready yet. Go back to the process page and wait for completion.',
    'sim.config_title': 'CONFIGURE OASIS SIMULATION',
    'sim.field_agents': 'SYNTHETIC AGENTS',
    'sim.field_agents_hint': '3\u2013120 personas. Default 40.',
    'sim.field_rounds': 'OASIS ROUNDS',
    'sim.field_model': 'SIMULATION MODEL',
    'sim.field_model_hint':
        'Used for agent LLM reactions during the simulation.',
    'sim.field_model_hint_static':
        'Static demo: precomputed output, model locked to GPT-4o.',
    'sim.eyebrow_step': 'STEP 03 \u00B7 OASIS',
    'sim.report_unlocks': 'Report and interaction unlock after the simulation.',
    'report.locked_title': 'Report not yet unlocked',
    'report.locked_body':
        'The final report opens after the OASIS simulation. The base report is already there, but step 3 is missing.',
    'report.go_sim_cta': 'GO TO SIMULATION \u2192',
    'sim.field_rounds_hint': '1\u201310 interaction rounds. Default 4.',
    'sim.starting': 'STARTING\u2026',
    'sim.launch_cta': 'START SIMULATION \u2192',
    'sim.open_report_cta': 'OPEN REPORT \u2192',
    'sim.retry': 'RETRY',
    'sim.failed_label': 'SIMULATION FAILED',
    'sim.unknown_error': 'Unknown error',
    'sim.kpi_profiles': 'PROFILES',
    'sim.kpi_actions': 'ACTIONS',
    'sim.kpi_zep': 'ZEP',
};

const DICTS: Record<Locale, Dict> = { it: IT, en: EN };

interface I18nCtx {
    locale: Locale;
    setLocale: (l: Locale) => void;
    t: (key: string, fallback?: string) => string;
}

const Ctx = createContext<I18nCtx | null>(null);

const STORAGE_KEY = 'miroedo.locale';

export function I18nProvider({ children }: { children: ReactNode }) {
    const [locale, setLocaleState] = useState<Locale>('en');

    useEffect(() => {
        try {
            const stored = window.localStorage.getItem(STORAGE_KEY);
            if (stored === 'it' || stored === 'en') {
                setLocaleState(stored);
                return;
            }
            // No stored preference → use browser language hint
            const nav = window.navigator?.language?.toLowerCase() ?? '';
            if (nav.startsWith('it')) setLocaleState('it');
            else setLocaleState('en');
        } catch {
            // ignore
        }
    }, []);

    const setLocale = useCallback((l: Locale) => {
        setLocaleState(l);
        try {
            window.localStorage.setItem(STORAGE_KEY, l);
        } catch {
            // ignore
        }
    }, []);

    const t = useCallback(
        (key: string, fallback?: string) => {
            const d = DICTS[locale] ?? DICTS.en;
            return d[key] ?? fallback ?? key;
        },
        [locale],
    );

    const value = useMemo(
        () => ({ locale, setLocale, t }),
        [locale, setLocale, t],
    );
    return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useT() {
    const ctx = useContext(Ctx);
    if (!ctx) throw new Error('useT must be used inside <I18nProvider>');
    return ctx;
}
