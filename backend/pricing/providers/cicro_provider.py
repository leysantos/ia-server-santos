from pricing.providers._tabular import TabularPriceProvider


class CicroProvider(TabularPriceProvider):
    """SICRO / CICRO — composições rodoviárias e infra."""

    name = "cicro"
    label = "CICRO/SICRO"
