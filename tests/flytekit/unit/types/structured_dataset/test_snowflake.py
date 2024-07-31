import mock
import pytest
from typing_extensions import Annotated
import sys

from flytekit import StructuredDataset, kwtypes, task, workflow

@pytest.mark.skipif("pandas" not in sys.modules, reason="Pandas is not installed.")
@mock.patch("flytekit.types.structured.snowflake.get_private_key", return_value="pb")
@mock.patch("snowflake.connector.connect")
def test_sf_wf(mock_connect, mock_get_private_key):
    import pandas as pd
    pd_df = pd.DataFrame({"Name": ["Tom", "Joseph"], "Age": [20, 22]})
    my_cols = kwtypes(Name=str, Age=int)

    @task
    def gen_df() -> Annotated[pd.DataFrame, my_cols, "parquet"]:
        return pd_df

    @task
    def t1(df: pd.DataFrame) -> Annotated[StructuredDataset, my_cols]:
        return StructuredDataset(
            dataframe=df,
            uri="snowflake://dummy_user/dummy_account/COMPUTE_WH/FLYTEAGENT/PUBLIC/TEST"
        )

    @task
    def t2(sd: Annotated[StructuredDataset, my_cols]) -> pd.DataFrame:
        return sd.open(pd.DataFrame).all()

    @workflow
    def wf() -> pd.DataFrame:
        df = gen_df()
        sd = t1(df=df)
        return t2(sd=sd)

    class mock_dataframe:
        def to_dataframe(self):
            return pd.DataFrame({"Name": ["Tom", "Joseph"], "Age": [20, 22]})

    mock_connect_instance = mock_connect.return_value
    mock_coursor_instance = mock_connect_instance.cursor.return_value
    mock_coursor_instance.fetch_pandas_all.return_value = mock_dataframe().to_dataframe()

    assert wf().equals(pd_df)
