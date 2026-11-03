"""Nomes de aeroportos e REGIOES prontas. Troque o destino do radar com /regiao no Telegram."""
from __future__ import annotations

NOMES = {
    # America do Sul
    "SCL": "Santiago", "EZE": "Buenos Aires (Ezeiza)", "AEP": "Buenos Aires (Aeroparque)",
    "MVD": "Montevidéu", "LIM": "Lima", "ASU": "Assunção", "COR": "Córdoba", "MDZ": "Mendoza",
    "BOG": "Bogotá", "MDE": "Medellín", "CTG": "Cartagena", "UIO": "Quito", "CUZ": "Cusco",
    "LPB": "La Paz", "VVI": "Santa Cruz", "BRC": "Bariloche", "USH": "Ushuaia",
    "FTE": "El Calafate", "PUQ": "Punta Arenas", "GYE": "Guayaquil", "CCS": "Caracas",
    "SLA": "Salta", "IPC": "Ilha de Páscoa", "CLO": "Cali",
    # Brasil
    "GIG": "Rio (Galeão)", "SDU": "Rio (Santos Dumont)", "SSA": "Salvador", "REC": "Recife",
    "FOR": "Fortaleza", "BSB": "Brasília", "CNF": "Belo Horizonte", "POA": "Porto Alegre",
    "CWB": "Curitiba", "FLN": "Florianópolis", "MAO": "Manaus", "BEL": "Belém", "NAT": "Natal",
    "MCZ": "Maceió", "GYN": "Goiânia", "VIX": "Vitória", "CGB": "Cuiabá", "IGU": "Foz do Iguaçu",
    "JPA": "João Pessoa", "AJU": "Aracaju", "SLZ": "São Luís", "FEN": "Fernando de Noronha",
    # America Central / Caribe / Mexico
    "PTY": "Panamá", "SJO": "San José (CR)", "GUA": "Guatemala", "SAL": "San Salvador",
    "PUJ": "Punta Cana", "CUN": "Cancún", "MEX": "Cidade do México", "HAV": "Havana",
    "SDQ": "Santo Domingo", "AUA": "Aruba", "CUR": "Curaçao", "MBJ": "Montego Bay",
    # America do Norte
    "MIA": "Miami", "MCO": "Orlando", "JFK": "Nova York (JFK)", "EWR": "Nova York (Newark)",
    "BOS": "Boston", "ORD": "Chicago", "ATL": "Atlanta", "DFW": "Dallas", "LAX": "Los Angeles",
    "SFO": "San Francisco", "IAD": "Washington", "YYZ": "Toronto", "YUL": "Montreal",
    "LAS": "Las Vegas", "SEA": "Seattle", "FLL": "Fort Lauderdale",
    # Europa
    "LIS": "Lisboa", "OPO": "Porto", "MAD": "Madri", "BCN": "Barcelona", "CDG": "Paris",
    "FCO": "Roma", "MXP": "Milão", "LHR": "Londres", "FRA": "Frankfurt", "AMS": "Amsterdã",
    "ZRH": "Zurique", "VIE": "Viena", "ATH": "Atenas", "IST": "Istambul", "DUB": "Dublin",
    "MUC": "Munique", "BRU": "Bruxelas", "CPH": "Copenhague", "WAW": "Varsóvia", "PRG": "Praga",
    "BUD": "Budapeste",
    # Asia / Oriente Medio
    "NRT": "Tóquio (Narita)", "HND": "Tóquio (Haneda)", "ICN": "Seul", "PVG": "Xangai",
    "HKG": "Hong Kong", "SIN": "Singapura", "BKK": "Bangkok", "DEL": "Délhi", "BOM": "Mumbai",
    "DXB": "Dubai", "DOH": "Doha", "KUL": "Kuala Lumpur", "MNL": "Manila", "TPE": "Taipé",
    "CGK": "Jacarta", "HAN": "Hanói", "SGN": "Ho Chi Minh", "TLV": "Tel Aviv", "AUH": "Abu Dhabi",
    # Africa
    "JNB": "Joanesburgo", "CPT": "Cidade do Cabo", "LOS": "Lagos", "ADD": "Adis Abeba",
    "CAI": "Cairo", "CMN": "Casablanca", "NBO": "Nairóbi", "ACC": "Acra", "LAD": "Luanda",
    "MPM": "Maputo",
    # Oceania
    "SYD": "Sydney", "MEL": "Melbourne", "AKL": "Auckland", "BNE": "Brisbane", "PER": "Perth",
    "NAN": "Fiji",
}

REGIOES = {
    "america_do_sul": ["SCL", "EZE", "AEP", "MVD", "LIM", "ASU", "COR", "MDZ", "BOG", "MDE", "CTG",
                       "UIO", "CUZ", "LPB", "VVI", "BRC", "USH", "FTE", "PUQ", "GYE"],
    "brasil": ["GIG", "SSA", "REC", "FOR", "BSB", "CNF", "POA", "CWB", "FLN", "MAO", "BEL", "NAT",
               "MCZ", "GYN", "VIX", "CGB", "IGU", "JPA", "AJU", "SLZ", "FEN"],
    "america_central": ["PTY", "SJO", "GUA", "SAL", "PUJ", "CUN", "MEX", "HAV", "SDQ", "AUA", "CUR", "MBJ"],
    "america_norte": ["MIA", "MCO", "JFK", "EWR", "BOS", "ORD", "ATL", "DFW", "LAX", "SFO", "IAD",
                      "YYZ", "YUL", "LAS", "SEA", "FLL"],
    "europa": ["LIS", "OPO", "MAD", "BCN", "CDG", "FCO", "MXP", "LHR", "FRA", "AMS", "ZRH", "VIE",
               "ATH", "IST", "DUB", "MUC", "BRU", "CPH", "WAW", "PRG", "BUD"],
    "asia": ["NRT", "HND", "ICN", "PVG", "HKG", "SIN", "BKK", "DEL", "BOM", "DXB", "DOH", "KUL",
             "MNL", "TPE", "CGK", "HAN", "SGN", "TLV", "AUH"],
    "africa": ["JNB", "CPT", "LOS", "ADD", "CAI", "CMN", "NBO", "ACC", "LAD", "MPM"],
    "oceania": ["SYD", "MEL", "AKL", "BNE", "PER", "NAN"],
}
REGIOES["mundo"] = [c for r in REGIOES.values() for c in r]

ALIAS = {
    "sul": "america_do_sul", "americadosul": "america_do_sul", "latam": "america_do_sul",
    "america_sul": "america_do_sul", "central": "america_central", "americacentral": "america_central",
    "norte": "america_norte", "eua": "america_norte", "americadonorte": "america_norte",
    "america_do_norte": "america_norte", "oriente": "asia", "todos": "mundo", "world": "mundo",
}


def regiao(nome_: str) -> str | None:
    k = nome_.strip().lower().replace("-", "_").replace("á", "a").replace("ã", "a").replace("é", "e")
    k = ALIAS.get(k, k)
    return k if k in REGIOES else None


def nome(code: str) -> str:
    return NOMES.get(code.upper(), code.upper())
