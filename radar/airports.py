NOMES = {
    "SCL": "Santiago", "EZE": "Buenos Aires (Ezeiza)", "AEP": "Buenos Aires (Aeroparque)",
    "MVD": "Montevidéu", "LIM": "Lima", "ASU": "Assunção", "COR": "Córdoba", "MDZ": "Mendoza",
    "BOG": "Bogotá", "MDE": "Medellín", "CTG": "Cartagena", "UIO": "Quito", "CUZ": "Cusco",
    "LPB": "La Paz", "VVI": "Santa Cruz", "PTY": "Panamá", "BRC": "Bariloche", "USH": "Ushuaia",
    "FTE": "El Calafate", "PUQ": "Punta Arenas", "GYE": "Guayaquil", "CCS": "Caracas",
    "SJO": "San José", "PUJ": "Punta Cana", "CUN": "Cancún", "MEX": "Cidade do México",
    "SLA": "Salta", "IGR": "Foz Argentina", "MAO": "Manaus", "CCP": "Concepción",
}


def nome(code: str) -> str:
    return NOMES.get(code.upper(), code.upper())
