import cdsapi

dataset = "projections-cmip6"
request = {
    "experiment": "ssp2_4_5",
    "variable": "air_temperature",
    "model": "cnrm_cm6_1",
    "month": [
        "01", "02", "03",
        "04", "05", "06",
        "07", "08", "09",
        "10", "11", "12"
    ],
    "year": ["2050", "2100"]
}

client = cdsapi.Client()
client.retrieve(dataset, request).download()
