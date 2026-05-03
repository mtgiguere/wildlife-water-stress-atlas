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

2. IconLayer (occurrences) — the story. Each icon is an elephant
   occurrence record. Pickable so users can hover to see year, species,
   and coordinates in a tooltip. Icon served from Streamlit static folder
   (same-origin, no CORS issues).

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

# Icon layer — served from Streamlit static folder (same-origin, no CORS)
ICON_URL = "app/static/elephant.png"
ICON_SIZE = 64        # pixel dimensions of the source image
ICON_SCALE = 2       # render scale multiplier — increase to make icons bigger


# ---------------------------------------------------------------------------
# Layer builders
# ---------------------------------------------------------------------------


def build_water_layer(gdf: gpd.GeoDataFrame) -> list[pdk.Layer]:
    """
    Build PyDeck layers for water sources.

    Returns two layers:
    - GeoJsonLayer for line geometries (rivers)
    - PolygonLayer for polygon geometries (lakes, wetlands, pans)

    Splitting by geometry type gives us explicit fill control over
    polygons which GeoJsonLayer struggles with on dark basemaps.
    """
    simplified = gdf.copy()
    simplified["geometry"] = simplified.geometry.simplify(0.01)
    simplified = simplified[~simplified.geometry.is_empty].copy()

    # Split by geometry type
    lines = simplified[simplified.geometry.geom_type == "LineString"].copy()
    polygons = simplified[simplified.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()

    layers = []

    # River lines
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

    # Lake/wetland polygons — using PolygonLayer for explicit fill
    if not polygons.empty:
        # PolygonLayer needs coordinates as lists
        polygons["coordinates"] = polygons.geometry.apply(
            lambda g: list(g.exterior.coords)
            if g.geom_type == "Polygon"
            else list(g.geoms[0].exterior.coords)
        )
        records = polygons[["coordinates"]].to_dict("records")

        layers.append(
            pdk.Layer(
                type="PolygonLayer",
                data=records,
                get_polygon="coordinates",
                get_fill_color=WATER_COLOR,
                get_line_color=WATER_COLOR,
                get_line_width=100,
                pickable=False,
                filled=True,
                stroked=True,
                extruded=False,
            )
        )

    return layers


def build_occurrences_layer(gdf: gpd.GeoDataFrame) -> pdk.Layer:
    """
    Build a PyDeck IconLayer for species occurrence points.

    Uses IconLayer to display the elephant icon served from Streamlit's
    static folder — same-origin so no CORS issues.

    IMPORTANT: deck.gl IconLayer requires icon_data to be embedded in
    each data record, not passed as a layer-level property. We inject
    the icon_data dict into every record before building the layer.

    The layer IS pickable — users can hover over icons to see
    species, year, and coordinates in a tooltip.

    Args:
        gdf: Occurrences GeoDataFrame with geometry and year columns.
             Can be empty (no records for selected year) — handled
             gracefully by returning a valid layer with no data.

    Returns:
        pdk.Layer configured as an IconLayer.
    """
    # Icon definition — must be embedded in each record for deck.gl IconLayer
    icon_data = {
        "url": ICON_URL,
        "width": ICON_SIZE,
        "height": ICON_SIZE,
        "anchorY": ICON_SIZE,  # anchor at bottom of icon
    }

    if not gdf.empty:
        data = gdf.copy()
        data["longitude"] = data.geometry.x
        data["latitude"] = data.geometry.y
        cols = ["longitude", "latitude", "year"]
        if "species" in data.columns:
            cols.append("species")
        records = data[cols].to_dict("records")

        # Embed icon_data into every record — required by deck.gl IconLayer
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

    Dark mapstyle makes the cyan water layer and elephant icons
    pop dramatically — better contrast than the light voyager style.
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
