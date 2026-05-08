"""
map.py

PyDeck map component builder for the Wildlife Water Stress Atlas.

WHY PYDECK:
-----------
PyDeck (deck.gl) handles large datasets efficiently via WebGL rendering.
With 20,000+ elephant occurrence points and thousands of water polygons,
matplotlib would be slow and Folium would struggle. PyDeck renders
everything on the GPU.

LAYER DESIGN:
-------------
Two layers compose the map:

1. GeoJsonLayer (water) — background context layer showing rivers,
   wetlands, pans, and floodplains. Not interactive — it's reference
   data, not the story.

2. IconLayer (occurrences) — the story. Each icon is a species
   occurrence record. Pickable so users can hover to see year, species,
   and coordinates in a tooltip. Icon path is passed dynamically from
   SPECIES_CONFIG so switching species automatically switches the icon.
   Icons served from Streamlit static folder (same-origin, no CORS).

AFRICA VIEW:
------------
Initial view is centered on Africa (lat=0, lon=20) at zoom=3 which
shows the full continent with reasonable detail.
"""

import json

import geopandas as gpd
import pydeck as pdk

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Africa center and zoom — shows full continent comfortably
AFRICA_LATITUDE = 0.0
AFRICA_LONGITUDE = 20.0
AFRICA_ZOOM = 3

# Water layer styling — bright cyan-blue, visible on dark background
WATER_COLOR = [0, 180, 255, 200]

# Icon layer sizing
ICON_SIZE = 64  # pixel dimensions of the source image
ICON_SCALE = 2  # render scale multiplier — increase to make icons bigger


# ---------------------------------------------------------------------------
# Layer builders
# ---------------------------------------------------------------------------


def build_water_layer(gdf: gpd.GeoDataFrame) -> list[pdk.Layer]:
    """
    Build PyDeck layers for water sources.

    Returns two layers:
    - GeoJsonLayer for line geometries (rivers)
    - GeoJsonLayer for polygon geometries (lakes, wetlands, pans)

    Using GeoJsonLayer for both types handles MultiPolygon geometries
    (e.g. Lake Victoria) correctly without manual coordinate extraction.
    Previously used PolygonLayer for polygons but that required extracting
    exterior coordinates which failed on MultiPolygon geometries — Lake
    Victoria rendered as a thin line instead of a filled polygon.

    Args:
        gdf: Water GeoDataFrame with normalized schema in EPSG:4326.

    Returns:
        List of pdk.Layer objects — one per geometry type present.
        Empty list if input GeoDataFrame is empty.
    """
    simplified = gdf.copy()
    simplified["geometry"] = simplified.geometry.simplify(0.01)
    simplified = simplified[~simplified.geometry.is_empty].copy()

    # Split by geometry type — different layer configs needed for lines vs polygons
    lines = simplified[simplified.geometry.geom_type == "LineString"].copy()
    polygons = simplified[simplified.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()

    layers = []

    # River lines — GeoJsonLayer with stroke only, no fill
    if not lines.empty:
        geojson = json.loads(lines.to_json())
        layers.append(
            pdk.Layer(
                type="GeoJsonLayer",
                data=geojson,
                get_line_color=WATER_COLOR,
                get_line_width=300,
                pickable=False,
                stroked=True,
                filled=False,
            )
        )

    # Lake/wetland polygons — GeoJsonLayer with fill
    # GeoJsonLayer handles MultiPolygon natively — no coordinate extraction needed
    if not polygons.empty:
        geojson = json.loads(polygons.to_json())
        layers.append(
            pdk.Layer(
                type="GeoJsonLayer",
                data=geojson,
                get_fill_color=WATER_COLOR,
                get_line_color=WATER_COLOR,
                get_line_width=100,
                pickable=False,
                filled=True,
                stroked=True,
            )
        )

    return layers


def build_occurrences_layer(
    gdf: gpd.GeoDataFrame,
    icon_path: str = "app/static/Creative-Tail-Animal-elephant.svg.png",
) -> pdk.Layer:
    """
    Build a PyDeck IconLayer for species occurrence points.

    Uses IconLayer to display species-specific icons served from
    Streamlit's static folder — same-origin so no CORS issues.

    The icon_path is passed dynamically from SPECIES_CONFIG so switching
    species in the sidebar automatically switches the map icon without
    any code changes — just a config entry.

    IMPORTANT: deck.gl IconLayer requires icon_data to be embedded in
    each data record, not passed as a layer-level property. We inject
    the icon_data dict into every record before building the layer.

    Args:
        gdf       : Occurrences GeoDataFrame with geometry and year columns.
                    Can be empty (no records for selected year) — handled
                    gracefully by returning a valid layer with no data.
        icon_path : Path to the icon served from Streamlit's static folder.
                    Format: "app/static/{filename}"
                    Defaults to elephant icon for backwards compatibility.

    Returns:
        pdk.Layer configured as an IconLayer.
    """
    # Icon definition — must be embedded in each record for deck.gl IconLayer.
    # anchorY set to ICON_SIZE anchors the icon at its bottom edge so it
    # sits ON the coordinate point rather than floating above it.
    icon_data = {
        "url": icon_path,
        "width": ICON_SIZE,
        "height": ICON_SIZE,
        "anchorY": ICON_SIZE,
    }

    if not gdf.empty:
        data = gdf.copy()
        data["longitude"] = data.geometry.x
        data["latitude"] = data.geometry.y
        cols = ["longitude", "latitude", "year"]
        if "species" in data.columns:
            cols.append("species")
        records = data[cols].to_dict("records")

        # Embed icon_data into every record — required by deck.gl IconLayer.
        # This is not redundant — deck.gl looks up icon_data per-record,
        # not as a layer-level property. Without this, icons don't render.
        for record in records:
            record["icon_data"] = icon_data
    else:
        records = []

    return pdk.Layer(
        type="IconLayer",
        data=records,
        get_icon="icon_data",
        get_position=["longitude", "latitude"],
        get_size=ICON_SCALE,
        size_scale=10,
        pickable=True,
    )


def build_deck(
    water_layers: list[pdk.Layer],
    occurrences_layer: pdk.Layer,
) -> pdk.Deck:
    """
    Assemble the final PyDeck Deck with dark CARTO basemap.

    Dark basemap makes the cyan water layer and species icons
    pop dramatically — better contrast than the light voyager style.
    Orange/coloured icons on dark = immediately readable at zoom 3.

    Args:
        water_layers      : List of water layers from build_water_layer().
        occurrences_layer : Species occurrence layer from build_occurrences_layer().

    Returns:
        pdk.Deck ready to pass to st.pydeck_chart().
    """
    view_state = pdk.ViewState(
        latitude=AFRICA_LATITUDE,
        longitude=AFRICA_LONGITUDE,
        zoom=AFRICA_ZOOM,
        pitch=0,
        bearing=0,
    )

    return pdk.Deck(
        layers=water_layers + [occurrences_layer],
        initial_view_state=view_state,
        tooltip={"text": "Year: {year}\nSpecies: {species}"},
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    )
