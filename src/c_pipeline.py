"""Track C entry point for `make c`: parcel → cell link, then the yield model and C1 CSV."""
from src import c_model, c_weather
from src.db import connect


def main() -> None:
    con = connect()
    c_weather.build_parcel_cell(con)
    con.close()
    c_model.main()


if __name__ == "__main__":
    main()
