from pathlib import Path
from .exceptions import OmniLoadError

import pandas as pd

COLUMN_NAMES = [
    "year",
    "day_of_year",
    "hour",
    "bartels_rotation",
    "imf_spacecraft_id",
    "plasma_spacecraft_id",
    "imf_sample_count",
    "plasma_sample_count",
    "b_magnitude_mean_nt",
    "b_vector_magnitude_nt",
    "b_latitude_gse_deg",
    "b_longitude_gse_deg",
    "bx_gse_nt",
    "by_gse_nt",
    "bz_gse_nt",
    "by_gsm_nt",
    "bz_gsm_nt",
    "sigma_b_magnitude_nt",
    "sigma_b_vector_nt",
    "sigma_bx_gse_nt",
    "sigma_by_gse_nt",
    "sigma_bz_gse_nt",
    "proton_temperature_k",
    "proton_density_cm3",
    "solar_wind_speed_kms",
    "flow_longitude_deg",
    "flow_latitude_deg",
    "alpha_proton_ratio",
    "flow_pressure_npa",
    "sigma_proton_temperature_k",
    "sigma_proton_density_cm3",
    "sigma_solar_wind_speed_kms",
    "sigma_flow_longitude_deg",
    "sigma_flow_latitude_deg",
    "sigma_alpha_proton_ratio",
    "electric_field_mvm",
    "plasma_beta",
    "alfven_mach_number",
    "kp_x10",
    "sunspot_number",
    "dst_nt",
    "ae_nt",
    "proton_flux_gt_1mev",
    "proton_flux_gt_2mev",
    "proton_flux_gt_4mev",
    "proton_flux_gt_10mev",
    "proton_flux_gt_30mev",
    "proton_flux_gt_60mev",
    "magnetospheric_flux_flag",
    "ap_nt",
    "f107_sfu",
    "pcn",
    "al_nt",
    "au_nt",
    "magnetosonic_mach_number",
]


def load_omni(path: Path) -> pd.DataFrame:
    """Lee un archivo horario de OMNI y asigna nombres a sus columnas."""

    # Comprobar que el archivo existe.
    if not path.is_file():
        raise OmniLoadError(f"No existe el archivo: {path}")

    # Leer el archivo y tratar el caso de archivo vacío.
    try:
        df = pd.read_csv(path, sep=r"\s+", header=None)
    except pd.errors.EmptyDataError as error:
        raise OmniLoadError(f"El archivo está vacío: {path}") from error

    # Comprobar la cantidad de columnas antes de nombrarlas.
    if df.shape[1] != len(COLUMN_NAMES):
        raise OmniLoadError(
            f"Se esperaban {len(COLUMN_NAMES)} columnas, "
            f"pero el archivo contiene {df.shape[1]}"
        )

    df.columns = COLUMN_NAMES
    return df