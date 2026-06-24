from pricing.providers._tabular import TabularPriceProvider


class DpSeminfProvider(TabularPriceProvider):
    """DP/SEMINF — composições fechadas importadas da planilha regional."""

    name = "dp_seminf"
    label = "DP/SEMINF"
