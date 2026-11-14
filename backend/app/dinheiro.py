"""Dinheiro sem erro de arredondamento (RF19).

Regras do projeto (docs/contratos.md):
- Banco: NUMERIC(12,2). Python: Decimal. Nunca float.
- JSON: texto decimal com duas casas ("150.00"), na entrada e na saida.

ler(): texto recebido -> Decimal, recusando o que exigiria arredondar.
texto(): Decimal -> "150.00" para as respostas.
"""

from decimal import Decimal, InvalidOperation

CENTAVO = Decimal("0.01")
MAXIMO = Decimal("9999999999.99")  # capacidade de NUMERIC(12,2)


def ler(valor: str) -> Decimal:
    """Converte texto em Decimal positivo com no maximo duas casas.

    Levanta ValueError (vira 422 entrada_invalida nas rotas). Nunca arredonda:
    "10.999" e recusado, nao vira "11.00".
    """
    if not isinstance(valor, str):
        raise ValueError("valor deve ser texto, ex.: \"150.00\"")
    try:
        numero = Decimal(valor.strip())
    except InvalidOperation:
        raise ValueError("valor invalido") from None
    if not numero.is_finite() or numero <= 0:
        raise ValueError("valor deve ser positivo")
    if numero > MAXIMO:  # antes do quantize: numeros enormes ("1e400") quebrariam o quantize
        raise ValueError("valor alto demais")
    if numero != numero.quantize(CENTAVO):
        raise ValueError("valor pode ter no maximo duas casas decimais")
    return numero.quantize(CENTAVO)


def texto(valor: Decimal) -> str:
    """Decimal -> "123.45" (sempre duas casas, sem notacao cientifica)."""
    return f"{valor.quantize(CENTAVO):f}"
