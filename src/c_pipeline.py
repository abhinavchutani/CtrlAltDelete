"""Track C entry point for `make c`: parcel → cell link, stage features, yield model + C1 CSV, C2 ensemble, C3 € risk."""
from src import c_ensemble, c_euro, c_features, c_model, c_weather
from src.db import connect


def main() -> None:
    con = connect()
    c_weather.build_parcel_cell(con)
    c_features.write(con, c_features.build(con))
    con.close()
    c_model.main()
    c_ensemble.main()
    c_euro.main()


if __name__ == "__main__":
    main()
