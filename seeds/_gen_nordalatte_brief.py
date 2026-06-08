"""
Genera il PDF brief crisis-recall per il secondo case study MiroEdo.
Brand fittizio: NordaLatte (azienda lattiero-casearia del Nord Italia).
Scenario: recall lotti yogurt per sospetta contaminazione Listeria.
Tono: brief strategico aziendale stile consulenza, ~4 pagine.
"""

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

OUT_PATH = "/Users/Edoardo.Di.Sabatino/Portfolio/AI-Project/Personal/MiroEdo/seeds/nordalatte_recall_brief.pdf"

# ---------- Styles ----------
styles = getSampleStyleSheet()
H1 = ParagraphStyle(
    "H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
    fontSize=20, leading=24, spaceAfter=10, textColor=colors.HexColor("#111111"),
)
H2 = ParagraphStyle(
    "H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
    fontSize=13, leading=16, spaceBefore=14, spaceAfter=6,
    textColor=colors.HexColor("#a01818"),
)
H3 = ParagraphStyle(
    "H3", parent=styles["Heading3"], fontName="Helvetica-Bold",
    fontSize=11, leading=14, spaceBefore=8, spaceAfter=4,
    textColor=colors.HexColor("#333333"),
)
BODY = ParagraphStyle(
    "Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5,
    leading=14.5, alignment=TA_JUSTIFY, spaceAfter=8,
)
QUOTE = ParagraphStyle(
    "Quote", parent=BODY, leftIndent=14, rightIndent=14, fontName="Helvetica-Oblique",
    fontSize=10, textColor=colors.HexColor("#444444"), spaceBefore=4, spaceAfter=8,
    borderColor=colors.HexColor("#a01818"), borderWidth=0, borderPadding=0,
)
META = ParagraphStyle(
    "Meta", parent=BODY, fontName="Helvetica-Oblique", fontSize=9.5,
    textColor=colors.HexColor("#666666"), spaceAfter=10,
)
SUBTITLE = ParagraphStyle(
    "Subtitle", parent=BODY, fontName="Helvetica-Oblique", fontSize=11,
    textColor=colors.HexColor("#555555"), alignment=TA_LEFT, spaceAfter=14,
)


def p(t, s=BODY):
    return Paragraph(t, s)


story = []

# ====================== PAG 1 — CONTESTO ======================
story += [
    p("NORDALATTE · BRIEF CRISIS-RECALL Q2 2026", META),
    p("Reazione di mercato al richiamo volontario lotti yogurt CremaPiù 0,1%", H1),
    p(
        "Documento interno · destinato a Direzione Marketing, PR, Customer Care, "
        "Insight &amp; Analytics. Periodo coperto: 03 marzo – 24 marzo 2026 (22 giorni).",
        SUBTITLE,
    ),

    p("01 · Sintesi esecutiva", H2),
    p(
        "Il 5 marzo 2026 NordaLatte ha annunciato il richiamo volontario di 14 lotti "
        "della linea <b>CremaPiù 0,1%</b> (yogurt magro funzionale) per sospetta "
        "contaminazione da Listeria monocytogenes rilevata in un campione prelevato "
        "nello stabilimento di Lodi. Il richiamo ha riguardato circa 380.000 "
        "confezioni distribuite tra Lombardia, Piemonte, Emilia-Romagna e Veneto "
        "nelle catene Esselunga, Conad, Coop e Pam Panorama.",
        BODY,
    ),
    p(
        "Nelle 72 ore successive all'annuncio si è osservata una prima ondata di "
        "menzioni negative concentrata su Twitter/X e Instagram (-0,68 sentiment medio), "
        "trainata dall'hashtag <b>#richiamonordalatte</b> e da una clip TikTok di una "
        "consumatrice milanese che mostrava il prodotto richiamato ancora in vendita "
        "il 6 marzo. Il sentiment ha iniziato a recuperare l'8 marzo, dopo la "
        "diretta LinkedIn dell'AD Carlo Manzoni e il comunicato congiunto con "
        "ATS Milano sulla negatività dei test di conferma su 11 lotti su 14.",
        BODY,
    ),
    p(
        "Al 24 marzo 2026 il sentiment aggregato è stabilizzato a <b>-0,12</b> "
        "(da -0,68 del picco), con un volume residuo di 35-50 mention/settimana "
        "(vs baseline pre-crisi di 80/sett). Il danno reputazionale è contenuto ma "
        "non chiuso: il driver «trasparenza nella supply chain» è emerso come tema "
        "ricorrente nelle conversazioni del consumatore informato, e tre testate "
        "verticali food (Dissapore, Il Cucchiaio d'Argento, Gambero Rosso) hanno "
        "annunciato approfondimenti per aprile.",
        BODY,
    ),

    p("02 · Timeline degli eventi rilevanti", H2),
    p(
        "Eventi narrativi della crisi (non aggregati con mention counts: "
        "per i volumi vedi sezione 04 e 05).",
        META,
    ),
    Table(
        [
            ["Data", "Evento", "Sentiment"],
            ["05 mar 2026", "Comunicato ufficiale di richiamo (h 14:30, sito + CS clienti)", "—"],
            ["05 mar 2026", "Prima ondata su Twitter/X, picco engagement nelle 4 ore successive", "-0,71"],
            ["06 mar 2026", "Clip TikTok @giulia_mi diventa virale: prodotto ancora a scaffale", "-0,82"],
            ["06 mar 2026", "Rilancio su Repubblica.it e Corriere food", "-0,58"],
            ["07 mar 2026", "Coop diffonde nota: ritiro completato sui punti vendita interessati", "-0,45"],
            ["08 mar 2026", "Diretta LinkedIn dell'AD Carlo Manzoni (22 minuti, senza moderatore)", "+0,12"],
            ["09 mar 2026", "Comunicato congiunto ATS Milano: undici lotti su quattordici risultati negativi", "+0,28"],
            ["12 mar 2026", "Articolo critico Dissapore: NordaLatte e la filiera opaca", "-0,34"],
            ["15 mar 2026", "Avvio campagna #FilieraTrasparente su LinkedIn organico", "+0,08"],
            ["18 mar 2026", "Rilascio video-tour dello stabilimento di Lodi su YouTube e Instagram", "+0,22"],
            ["22 mar 2026", "Test di conferma negativi su tutti i quattordici lotti", "+0,31"],
            ["24 mar 2026", "Stabilizzazione del volume di conversazione su livelli post-crisi", "-0,12"],
        ],
        colWidths=[2.6 * cm, 11.4 * cm, 2.2 * cm],
        repeatRows=1,
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#a01818")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]),
    ),
    Spacer(1, 4 * mm),

    p("02b · Volume mention aggregato per settimana", H3),
    p(
        "Serie storica del volume di conversazione (mention sui canali monitorati) "
        "nelle quattro settimane di osservazione. Dato grezzo, pre-clustering tematico.",
        BODY,
    ),
    Table(
        [
            ["Settimana", "Mention totali", "Sentiment medio"],
            ["02 mar – 08 mar 2026", "486", "-0,52"],
            ["09 mar – 15 mar 2026", "412", "-0,18"],
            ["16 mar – 22 mar 2026", "238", "-0,05"],
            ["23 mar – 24 mar 2026", "111", "-0,12"],
        ],
        colWidths=[5.6 * cm, 4.0 * cm, 4.0 * cm],
        repeatRows=1,
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#a01818")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]),
    ),
    PageBreak(),
]

# ====================== PAG 2 — VOICE OF MARKET ======================
story += [
    p("03 · Voice of market — campione di mention rappresentative", H2),
    p(
        "Selezione di 18 mention scelte per coprire i cluster di sentiment osservati. "
        "Tutti i nomi utente sono reali ma riportati in forma pseudonimizzata. "
        "Le quote in inglese provengono dal monitoraggio internazionale "
        "(testate food trade e analisti retail EU).",
        BODY,
    ),

    p("3.1 · Cluster rabbia consumatore storico (07–10 marzo)", H3),
    p("«Compro NordaLatte da 15 anni, mia figlia mangia solo CremaPiù. Stamattina ho buttato 4 vasetti. La fiducia non si ricompra con un comunicato.» — @anna_brescia, Instagram, 5 mar", QUOTE),
    p("«Ma scherziamo? Il richiamo lo apprendo da un post su FB, non da NordaLatte. Zero email, zero notifica nell'app. Imbarazzante.» — @marco_lecco, Twitter/X, 6 mar", QUOTE),
    p("«Listeria nel reparto frigo. Bambini. Anziani. Donne incinte. Non è uno scherzo, è negligenza industriale.» — @mamma_in_carriera, Instagram, 6 mar", QUOTE),
    p("«#richiamonordalatte è in tendenza e loro pubblicano la ricetta del tiramisù primaverile. Crisis management livello -10.» — @pr_critic_milano, Twitter/X, 7 mar", QUOTE),

    p("3.2 · Cluster recupero post-diretta LinkedIn AD (08–10 marzo)", H3),
    p("«Ho ascoltato la diretta di Manzoni. Onesta, niente legalese, niente colpa del fornitore. Ha detto «abbiamo sbagliato a comunicare tardi». Punto. Cambio idea sul brand.» — Luca Pirovano, LinkedIn (Director Supply Chain, settore retail), 8 mar", QUOTE),
    p("«Manzoni che fa il mea culpa in diretta senza slide e senza moderatore: questa è la nuova normalità del crisis comm. Take notes.» — @valentina_pr, Twitter/X, 9 mar", QUOTE),
    p("«NordaLatte AD does live LinkedIn admitting the recall PR delay. Italian dairy crisis-comm finally catching up to Nordic playbook.» — @nordic_retail_watch, Twitter/X (EN), 9 mar", QUOTE),

    p("3.3 · Cluster scetticismo strutturale e filiera (10–18 marzo)", H3),
    p("«La diretta è stata bella ma resta la domanda: come è arrivata la Listeria nello stabilimento? Vogliamo il report ATS pubblico, non il comunicato congiunto.» — Giorgia Rinaldi, LinkedIn (food blogger Dissapore), 10 mar", QUOTE),
    p("«NordaLatte parla di filiera corta ma il latte di CremaPiù da quale stalla viene? Il QR code sul vasetto rimanda al sito istituzionale, non al fornitore.» — @critic_food_italia, Instagram, 11 mar", QUOTE),
    p("«Listeria episode aside: NordaLatte's supply chain disclosure is below industry average. Carrefour FR publishes farm-level data, here we get a PDF press release.» — Andreas Hofer, LinkedIn (analyst, Retail Intelligence DACH), 12 mar", QUOTE),

    p("3.4 · Cluster di sostegno militante (10–20 marzo)", H3),
    p("«NordaLatte ha richiamato volontariamente prima che l'ATS lo imponesse. Questo è il sistema italiano che funziona. Smettetela di linciare.» — @consumatore_informato, Twitter/X, 10 mar", QUOTE),
    p("«Lavoro nel QC di un caseificio. Un campione positivo su quattordici lotti è statisticamente fisiologico. Il problema è la comunicazione, non la qualità.» — @qc_dairy_anon, Twitter/X, 11 mar", QUOTE),

    p("3.5 · Cluster competitor / opportunismo (8–15 marzo)", H3),
    p("«Anche noi facciamo yogurt magro funzionale. Anche noi tracciamo lotto per lotto. Anche noi pubblichiamo i report ATS in tempo reale. #LatteVero» — @latteverobio_official, Instagram, 8 mar (post sponsorizzato)", QUOTE),
    p("«Promo speciale CremaSnella -30% nei punti vendita Esselunga del Nord. La nostra qualità non si discute.» — @cremasnella_it, Twitter/X, 11 mar", QUOTE),
    PageBreak(),
]

# ====================== PAG 3 — ANALISI ======================
story += [
    p("04 · Cluster tematici e sentiment narrativo", H2),
    p(
        "Aggregando le 1.247 mention raccolte nel periodo di osservazione "
        "(03 mar–24 mar 2026), emergono quattro driver narrativi distinti, ciascuno "
        "con sua dinamica temporale e implicazioni operative differenti.",
        BODY,
    ),
    Table(
        [
            ["Driver narrativo", "Mention", "Sentiment", "Peak", "Stato"],
            ["Sicurezza alimentare percepita", "412", "-0,54", "06 mar", "in attenuazione"],
            ["Comunicazione di crisi (timing)", "318", "-0,38", "07 mar", "stabilizzato"],
            ["Trasparenza filiera / supply chain", "267", "-0,21", "12 mar", "emergente"],
            ["Leadership e accountability (AD)", "190", "+0,32", "09 mar", "positivo persistente"],
            ["Opportunismo competitor", "60", "neutro", "11 mar", "marginale"],
        ],
        colWidths=[6.3 * cm, 2.0 * cm, 2.2 * cm, 2.2 * cm, 3.5 * cm],
        repeatRows=1,
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#a01818")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]),
    ),
    Spacer(1, 4 * mm),

    p("4.1 · Lettura strategica", H3),
    p(
        "Il driver <b>«Sicurezza alimentare percepita»</b> ha esaurito la sua "
        "carica entro il 10 marzo grazie alla conferma ATS, ma ha lasciato un "
        "residuo di sfiducia presso il segmento «famiglie con bambini 0-6 anni», "
        "storicamente core target di CremaPiù. Le mention dirette di questo "
        "segmento sono crollate del 42% nelle settimane successive, e il monitoraggio "
        "delle reazioni alle nuove uscite di prodotto sarà l'indicatore principale "
        "del recupero reale.",
        BODY,
    ),
    p(
        "Il driver <b>«Comunicazione di crisi (timing)»</b> è il punto di "
        "vulnerabilità più dolente: la critica non è sul richiamo in sé "
        "(percepito come atto responsabile) ma sulla finestra di tre giorni tra "
        "scoperta interna (3 marzo, secondo le ricostruzioni stampa) e comunicato "
        "pubblico (5 marzo). La diretta LinkedIn dell'AD ha disinnescato il tema "
        "per gli stakeholder professionali ma resta latente nel consumatore retail.",
        BODY,
    ),
    p(
        "Il driver <b>«Trasparenza filiera»</b> è emergente e potenzialmente "
        "esplosivo. Non riguarda la crisi attuale ma una domanda strutturale che "
        "la crisi ha solo fatto emergere: «da quale stalla viene il latte CremaPiù?». "
        "Le testate verticali (Dissapore, Gambero Rosso) e gli analisti EU "
        "(Hofer su LinkedIn) stanno spingendo verso uno standard di disclosure "
        "farm-level che NordaLatte oggi non offre. Se il tema cresce, diventa il "
        "lascito reputazionale di lungo periodo della crisi.",
        BODY,
    ),
    p(
        "Il driver <b>«Leadership e accountability (AD)»</b> è l'unico positivo "
        "consistente. La scelta di Carlo Manzoni di esporsi in prima persona, "
        "senza moderatore, senza slide, è stata letta come segnale di onestà "
        "e ha generato il 28% delle reazioni positive del periodo. È un asset "
        "da capitalizzare nei prossimi 30 giorni con uscite mirate sui temi "
        "filiera / QC / standard sicurezza.",
        BODY,
    ),

    p("05 · Geo e canali rilevanti", H3),
    Table(
        [
            ["Canale", "% mention", "Sentiment medio", "Profilo audience"],
            ["Twitter / X", "38%", "-0,32", "early adopter, reattivo, polarizzato"],
            ["Instagram", "27%", "-0,21", "consumatore famiglia, visuale, emotivo"],
            ["LinkedIn", "19%", "+0,14", "professional, B2B, food trade, EU watchers"],
            ["TikTok", "9%", "-0,48", "GenZ, viralità rapida, drammatizzazione"],
            ["Blog / testate food", "7%", "-0,12", "verticali, lungo periodo, agenda-setting"],
        ],
        colWidths=[4.0 * cm, 2.4 * cm, 3.0 * cm, 6.8 * cm],
        repeatRows=1,
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#a01818")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (2, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]),
    ),
    Spacer(1, 3 * mm),
    p(
        "Distribuzione geografica: Lombardia 41%, Piemonte 14%, Emilia-Romagna 12%, "
        "Veneto 9%, Lazio 8%, resto Italia 11%, internazionale (EU) 5%. "
        "Il peso del Sud è marginale ma in crescita post-articolo Repubblica.it "
        "del 6 marzo, segnale che la crisi sta superando il bacino di distribuzione "
        "originario per via mediatica.",
        BODY,
    ),
    PageBreak(),
]

# ====================== PAG 4 — DOMANDE APERTE ======================
story += [
    p("06 · Stakeholder chiave da monitorare nelle prossime 4 settimane", H2),
    p(
        "Lista non esaustiva di account / testate / analisti la cui posizione "
        "nelle prossime settimane può inclinare la traiettoria del recupero "
        "reputazionale. Ordinati per influenza stimata sul segmento target.",
        BODY,
    ),
    Table(
        [
            ["Stakeholder", "Canale", "Influenza", "Posizione attuale"],
            ["Giorgia Rinaldi (Dissapore)", "LinkedIn / blog", "alta", "critica costruttiva, attende dati"],
            ["Andreas Hofer (Retail Intel DACH)", "LinkedIn", "media-alta", "scettico strutturale su filiera"],
            ["@mamma_in_carriera", "Instagram", "alta (segmento family)", "molto negativa, non recuperata"],
            ["@valentina_pr", "Twitter / X", "media (PR community)", "moderatamente positiva post-diretta"],
            ["Gambero Rosso (redazione)", "testata", "alta (verticali food)", "neutra, approfondimento in agenda"],
            ["@latteverobio_official", "Instagram", "media (competitor)", "opportunismo attivo, sponsorizza"],
            ["ATS Milano", "comunicati", "altissima (autorità)", "collaborativa, report finale atteso"],
        ],
        colWidths=[5.2 * cm, 3.2 * cm, 3.5 * cm, 4.3 * cm],
        repeatRows=1,
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#a01818")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]),
    ),

    p("07 · Domande aperte per la Direzione", H2),
    p(
        "Questo brief si chiude con quattro domande strategiche aperte. La risposta "
        "non è nei dati raccolti finora; richiede deliberazione cross-funzionale "
        "tra Marketing, PR, Insight, Supply Chain e Legal entro il <b>5 aprile 2026</b>.",
        BODY,
    ),
    p("Q1 — Comunicazione tardiva: emettiamo un comunicato di rettifica esplicito sulla finestra di tre giorni (3-5 marzo) per riconoscere il ritardo e disinnescare il driver permanentemente, o lasciamo decantare confidando che il tema si esaurisca da solo?", BODY),
    p("Q2 — Trasparenza filiera: portiamo avanti una vera policy di disclosure farm-level (stile Carrefour FR) entro Q3 2026, o ci limitiamo a campagne #FilieraTrasparente di awareness senza apertura strutturale dei dati?", BODY),
    p("Q3 — Rilancio prodotto: la linea CremaPiù torna a scaffale entro fine marzo con packaging invariato, oppure cogliamo l'occasione per un restage che includa visibilmente i nuovi protocolli QC (es. data e codice analisi sul vasetto)?", BODY),
    p("Q4 — Leadership: capitalizziamo il momentum positivo dell'AD Manzoni con una rubrica fissa LinkedIn (es. «Dietro le quinte di NordaLatte», mensile), o consideriamo l'esposizione del 8 marzo un evento una-tantum legato alla crisi?", BODY),

    Spacer(1, 6 * mm),
    p(
        "<i>Brief preparato da Direzione Insight &amp; Analytics NordaLatte · "
        "redazione 24 marzo 2026 · circolazione interna riservata.</i>",
        META,
    ),
]


# ---------- Build ----------
doc = SimpleDocTemplate(
    OUT_PATH,
    pagesize=A4,
    leftMargin=2.0 * cm,
    rightMargin=2.0 * cm,
    topMargin=1.8 * cm,
    bottomMargin=1.8 * cm,
    title="NordaLatte — Brief Crisis-Recall Q2 2026",
    author="MiroEdo Seed Generator",
)
doc.build(story)
print(f"OK: {OUT_PATH}")
