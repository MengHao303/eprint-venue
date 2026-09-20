"""Fold the free-text venue of a Publication info line onto a canonical name.

'ACM CCS 2026', 'CCS 2026', "ACM CCS'26", 'ACM-CCS 2026' and 'Proceedings of the
2026 ACM SIGSAC Conference on Computer and Communications Security' are all one
venue, so they are all matched to 'ACM CCS'. Rules are checked in order, so the
narrower ones (AsiaCCS, EuroS&P, USENIX WOOT) come before the broader ones.
"""
import re

# (canonical name, pattern matched against the normalised venue string)
RULES = [
    # --- IACR ---
    ("CRYPTO", r"\bcrypto\b"),
    ("EUROCRYPT", r"\beurocrypt\b"),
    ("ASIACRYPT", r"\basiacrypt\b"),
    ("TCHES", r"\btches\b|cryptographic hardware and embedded systems|\bches\b"),
    ("ToSC", r"\btosc\b|symmetric cryptology|\bfse\b|fast software encryption"),
    ("PKC", r"\bpkc\b|public[- ]key cryptography(?! workshop)"),
    ("TCC", r"\btcc\b|theory of cryptography conference"),
    ("CiC", r"\bcic\b|communications in cryptology"),
    ("Journal of Cryptology", r"\bjoc\b|journal of cryptology"),
    ("Real World Crypto", r"\brwc\b|real world crypto"),

    # --- journals ---
    ("IEEE TIFS", r"transactions on information forensics"),
    ("IEEE TDSC", r"transactions on dependable and secure"),
    ("IEEE TIT", r"transactions on information theory"),
    ("IEEE TC", r"transactions on computers\b"),
    ("IEEE TCAS", r"transactions on circuits and systems"),
    ("IEEE TNSM", r"transactions on network and service management"),
    ("IEEE Transactions on Networking", r"transactions on networking"),
    ("IEEE IoT Journal", r"internet of things journal"),
    ("IEEE Access", r"ieee access"),
    ("Proceedings of the IEEE", r"proceedings of the ieee"),
    ("Designs, Codes and Cryptography", r"design[s]?,? codes and cryptography"),
    ("Journal of Cryptographic Engineering", r"cryptographic engineering"),
    ("Cryptography and Communications", r"cryptography and communications"),
    ("Discrete Mathematics", r"discrete mathematics"),
    ("Discrete Applied Mathematics", r"\bdam\b|discrete applied mathematics"),
    ("Journal of Cybersecurity", r"journal of cybersecurity(?! and privacy)"),
    ("IEICE Transactions", r"ieice transactions"),
    ("Neurocomputing", r"neurocomputing"),
    ("MDPI Cryptography", r"mdpi cryptography"),
    ("MDPI JCP", r"journal of cybersecurity and privacy"),
    ("Journal of Computer Virology", r"computer virology"),

    # --- security conferences (narrow before broad) ---
    ("AsiaCCS", r"\basia[- ]?ccs\b|asia conference on computer and communications security"),
    ("USENIX WOOT", r"\bwoot\b"),
    ("OSDI", r"\bosdi\b"),
    ("USENIX Security", r"\busenix\b|\bsec ?'?2?6\b(?= symposium)"),
    ("EuroS&P", r"euro\s?s&p|european symposium on security and privacy"),
    ("IEEE S&P", r"ieee s&p|s&p\b|symposium on security and privacy|\boakland\b"),
    ("ACM CCS", r"\bacm[- ]?ccs\b|\bccs\b|conference on computer and communications security"),
    ("NDSS", r"\bndss\b|network and distributed system security"),
    ("ESORICS", r"\besorics\b|european symposium on research in computer security"),
    ("ACNS", r"\bacns\b|applied cryptography and network security"),
    ("PoPETs", r"\bpopets?\b|\bpets\b|privacy enhancing technologies"),
    ("IEEE CSF", r"\bcsf\b|computer security foundations"),
    ("SCN", r"\bscn\b|security and cryptography for networks"),
    ("PQCrypto", r"\bpqcrypto\b|post[- ]quantum cryptography conference"),
    ("SAC", r"\bsac\b|selected areas in cryptography"),
    ("Financial Cryptography", r"\bfc\b|financial cryptograph"),
    ("AFRICACRYPT", r"\bafricacrypt\b|cryptology in africa"),
    ("LATINCRYPT", r"\blatincrypt\b"),
    ("INDOCRYPT", r"\bindocrypt\b"),
    ("ACISP", r"\bacisp\b|australasian conference on information security"),
    ("ICICS", r"\bicics\b|international conference on information and communications security"),
    ("CANS", r"\bcans\b|cryptology and network security"),
    ("SECRYPT", r"\bsecrypt\b"),
    ("ITC", r"\bitc\b|information theoretic cryptography"),
    ("CT-RSA", r"\bct-?rsac?\b|cryptographers.? track"),
    ("RSA Conference", r"\brsac?\b conference|\brsac\b"),
    ("ProvSec", r"\bprovsec\b|provable and practical security"),
    ("ISPEC", r"\bispec\b|information security practice and experience"),
    ("ISC", r"\bisc\b|international conference on information security"),
    ("CSCML", r"\bcscml\b|cyber security, cryptology"),
    ("SSR", r"\bssr\b|security standardi[sz]ation research"),
    ("SecITC", r"\bsecitc\b"),
    ("DBSec", r"\bdbsec\b|data and applications security"),
    ("ARES", r"\bares\b|availability, reliability and security"),
    ("WPES", r"\bwpes\b|workshop on privacy in the electronic society"),
    ("AISec", r"\baisec\b|artificial intelligence and security"),
    ("STM", r"\bstm\b|security and trust management"),
    ("E-Vote-ID", r"e-?vote-?id"),
    ("SecureComm", r"\bsecurecomm\b"),
    ("WAIFI", r"\bwaifi\b|arithmetic of finite fields"),
    ("NuTMiC", r"\bnutmic\b"),
    ("CASCADE", r"\bcascade\b"),
    ("zkProof", r"zkproof"),
    ("SaTML", r"\bsatml\b|secure and trustworthy machine learning"),
    ("DSN", r"\bdsn\b|dependable systems and networks"),
    ("COMPSAC", r"\bcompsac\b"),
    ("ICDCS", r"\bicdcs\b|distributed computing systems"),
    ("SRDS", r"\bsrds\b|reliable distributed systems"),
    ("APKC", r"\bapkc\b"),
    ("AFT", r"\baft\b|advances in financial technolog"),
    ("CyberSecurity", r"\bcybersecurity\b conference|\bcybersecurity 20"),
    ("EICC", r"\beicc\b"),
    ("ESCAR", r"\bescar\b"),
    ("ICDSNE", r"\bicdsne\b"),
    ("ICISC", r"\bicisc\b"),


    # --- other conferences on the cyber security ranking list ---
    ("ACSAC", r"\bacsac\b|annual computer security applications"),
    ("RAID", r"\braid\b|research in attacks, intrusions"),
    ("WiSec", r"\bwisec\b|wireless and mobile network security"),
    ("CODASPY", r"\bcodaspy\b|data and application security and privacy"),
    ("SACMAT", r"\bsacmat\b|access control models"),
    ("CPSS", r"\bcpss\b|cyber-physical system security"),
    ("COSADE", r"\bcosade\b|constructive side-channel analysis"),
    ("FDTC", r"\bfdtc\b|fault diagnosis and tolerance"),
    ("DIMVA", r"\bdimva\b|detection of intrusions and malware"),
    ("Inscrypt", r"\binscrypt\b|information security and cryptology\b"),
    ("INDOCRYPT", r"\bindocrypt\b"),
    ("LATINCRYPT", r"\blatincrypt\b"),
    ("IWSEC", r"\biwsec\b"),
    ("IMACC", r"\bimacc\b|ima international conference on cryptography"),
    ("NSS", r"\bnss\b|network and system security"),
    ("NSPW", r"\bnspw\b|new security paradigms"),
    ("Pairing", r"\bpairing\b"),
    ("QCrypt", r"\bqcrypt\b"),
    ("SPACE", r"\bspace\b|security, privacy, and applied cryptography engineering"),
    ("WISA", r"\bwisa\b"),
    ("WCC", r"\bwcc\b|workshop on coding and cryptography"),
    ("SCIS", r"\bscis\b"),
    ("GameSec", r"\bgamesec\b|decision and game theory for security"),
    ("DFRWS", r"\bdfrws\b"),
    ("TrustCom", r"\btrustcom\b"),
    ("SecDev", r"\bsecdev\b"),
    ("IEEE CNS", r"\bcns\b|communications and network security"),
    ("IEEE CSR", r"\bcsr\b|cyber security and resilience"),
    ("IEEE QRS", r"\bqrs\b"),
    ("IEEE PRDC", r"\bprdc\b|pacific rim international symposium on dependable"),
    ("IEEE HASE", r"\bhase\b|high assurance systems engineering"),
    ("IEEE HST", r"\bhst\b|homeland security technologies"),
    ("IEEE DASC", r"\bdasc\b"),
    ("IEEE DSC", r"\bdsc\b|dependable and secure computing conference"),
    ("IEEE Malware", r"\bmalware\b conference|international conference on malicious"),
    ("PST", r"\bpst\b|privacy, security and trust"),
    ("PSD", r"\bpsd\b|privacy in statistical databases"),
    ("DPM", r"\bdpm\b|data privacy management"),
    ("FPS", r"\bfps\b|foundations and practice of security"),
    ("ESSoS", r"\bessos\b|engineering secure software"),
    ("EuroSec", r"\beurosec\b"),
    ("ICISS", r"\biciss\b|information systems security\b"),
    ("ICISSP", r"\bicissp\b"),
    ("ICDF2C", r"\bicdf2c\b|digital forensics and cyber crime"),
    ("CRITIS", r"\bcritis\b|critical information infrastructures security"),
    ("CRiSIS", r"\bcrisis\b|risks and security of internet"),
    ("CISIS", r"\bcisis\b|computational intelligence in security"),
    ("CBCrypto", r"\bcbcrypto\b|code-based cryptography"),
    ("ECC", r"\becc\b workshop|workshop on elliptic curve cryptography"),
    ("EDCC", r"\bedcc\b|european dependable computing"),
    ("SAFECOMP", r"\bsafecomp\b"),
    ("SIN", r"\bsin\b|security of information and networks"),
    ("SPW", r"\bspw\b|security protocols workshop"),
    ("VizSec", r"\bvizsec\b"),
    ("WEIS", r"\bweis\b|economics of information security"),
    ("WISTP", r"\bwistp\b"),
    ("SOUPS", r"\bsoups\b|usable privacy and security"),
    ("USENIX PEPR", r"\bpepr\b"),
    ("IWDW", r"\biwdw\b|digital watermarking"),
    ("NordSec", r"\bnordsec\b"),
    ("SAM", r"\bsam\b"),
    ("SecurWare", r"\bsecurware\b"),
    ("ICIMP", r"\bicimp\b"),
    ("IFIP SEC", r"\bifip[- ]sec\b|ifip international information security"),
    ("IFIP CIP", r"\bifip[- ]cip\b|critical infrastructure protection"),
    ("IFIP DF", r"\bifip[- ]df\b|advances in digital forensics"),
    ("IFIP HAISA", r"\bhaisa\b"),
    ("IFIP NTMS", r"\bntms\b"),
    ("IFIP TM", r"\bifip[- ]tm\b|trust management\b"),

    # --- theory ---
    ("STOC", r"\bstoc\b|symposium on theory of computing"),
    ("FOCS", r"\bfocs\b|foundations of computer science"),
    ("SODA", r"\bsoda\b"),
    ("ITCS", r"\bitcs\b|innovations in theoretical computer science"),
    ("PODC", r"\bpodc\b|principles of distributed computing"),
    ("DISC", r"\bdisc\b|symposium on distributed computing"),
    ("SSS", r"\bsss\b|stabilization, safety"),
    ("ANTS", r"\bants\b|algorithmic number theory"),
    ("ISIT", r"\bisit\b|symposium on information theory"),

    # --- machine learning ---
    ("ICML", r"\bicml\b"),
    ("NeurIPS", r"\bneurips\b|\bnips\b"),
    ("ICLR", r"\biclr\b"),
    ("AAAI", r"\baaai\b"),

    # --- hardware, architecture, EDA ---
    ("DAC", r"\bdac\b|design automation conference"),
    ("DATE", r"\bdate\b|design, automation and test"),
    ("HOST", r"\bhost\b|hardware oriented security and trust"),
    ("ICCAD", r"\biccad\b|computer[- ]aided design"),
    ("FPL", r"\bfpl\b|field[- ]programmable logic"),
    ("FCCM", r"\bfccm\b|field[- ]programmable custom computing"),
    ("ISCAS", r"\biscas\b|circuits and systems\b(?!.*transactions)"),
    ("ASAP", r"\basap\b|application[- ]specific systems, architectures"),
    ("HPCA", r"\bhpca\b|high performance computer architecture"),
    ("ICS", r"\bics\b|international conference on supercomputing"),
    ("ARITH", r"\barith\b|symposium on computer arithmetic"),
    ("VLSID", r"\bvlsid\b|conference on vlsi design"),
    ("ICPE", r"\bicpe\b|performance engineering"),
    ("ICBC", r"\bicbc\b|blockchain and cryptocurrency"),
    ("QCNC", r"\bqcnc\b"),
    ("PerCom", r"\bpercom\b|pervasive computing and communications"),

    # --- last resort: preprint servers and publishers ---
    ("Proceedings of the IEEE", r"^ieee$"),
    ("arXiv", r"\barxiv\b"),
    ("Springer", r"\bspringer\b|link\.springer\.com"),
]

RULES = [(name, re.compile(pat)) for name, pat in RULES]

# Venues left out of the site's venue filter: preprint servers, publishers and
# strings that are not really a publication venue. The papers themselves stay in
# the listing with their Publication info printed as the archive prints it —
# only the dropdown entry goes away. Add a canonical name here to hide it.
HIDDEN = {
    "arXiv",
    "Springer",
    "zkProof",
}

# Venues with fewer papers than this are also left out of the dropdown.
# 1 keeps every venue; 2 drops the one-off entries.
MIN_PAPERS = 1

# Only these venues are offered in the site's filter: the 22 ranked conferences
# on Jianying Zhou's cyber security ranking (fetched 2026-09-20),
# http://jianying.space/conference-ranking.html, plus a few IACR and theory
# venues kept on request. A "page:" comment marks a venue that page spells
# differently. Empty the set to offer every venue again.
ALLOWED = {
    # the 22 ranked conferences, in the page's order
    "IEEE S&P", "EUROCRYPT", "NDSS", "ACM CCS", "CRYPTO", "USENIX Security",
    "TCHES",                     # page: CHES
    "Financial Cryptography",    # page: FC
    "EuroS&P", "ACNS", "ACSAC", "AsiaCCS",
    "PoPETs",                    # page: PETS
    "ASIACRYPT", "PKC", "ESORICS",
    "ToSC",                      # page: FSE
    "WiSec", "RAID", "CT-RSA", "IEEE CSF", "TCC",
    # kept alongside the ranking
    "CiC", "Journal of Cryptology",
    "STOC", "FOCS", "PODC",
    "Designs, Codes and Cryptography",
}

# "(Eurocrypt affiliated event)" names someone else's conference, not the venue
AFFILIATION = re.compile(r"\([^)]*(?:affiliated|co-?located)[^)]*\)", re.I)

STRIP_PREFIX = re.compile(
    r"^(to appear (in|at)|accepted (at|to|in|for)|appeared (in|at)|published (in|at)|"
    r"in proceedings of( the)?|proceedings of( the)?|proceedings on|in|at)\s+", re.I)
YEARISH = re.compile(r"\b(?:19|20)\d{2,4}(?:\.\d+)?\b|['’]\d{2}\b|\b\d{1,3}(?:st|nd|rd|th)\b")


def normalise(raw):
    s = AFFILIATION.sub(" ", raw).lower()
    s = re.sub(r"(?<=[a-z])((?:19|20)\d{2})\b", r" \1", s)  # ICML2026 -> ICML 2026
    s = s.replace("’", "'").replace("‘", "'")
    s = re.sub(r"[–—]", "-", s)
    s = YEARISH.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" .,;:-")
    prev = None
    while prev != s:
        prev = s
        s = STRIP_PREFIX.sub("", s).strip()
    return s


def canonical(raw):
    """Canonical venue name for a raw venue string ('' if there is none)."""
    if not raw:
        return ""
    s = normalise(raw)
    if not s:
        return ""
    for name, pat in RULES:
        if pat.search(s):
            return name
    # a rule may depend on wording that normalising stripped ("Proceedings of the IEEE")
    low = AFFILIATION.sub(" ", raw).lower()
    for name, pat in RULES:
        if pat.search(low):
            return name
    # no rule matched: clean up the leading clause and title-case nothing
    s = re.split(r"[,;(]| - |\bvol\.|\blncs\b", raw)[0]
    s = YEARISH.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" .,;:-'\"")
    s = STRIP_PREFIX.sub("", s).strip()
    if len(s) > 46:
        s = s[:44].rstrip() + "…"
    return s or "Unspecified"
