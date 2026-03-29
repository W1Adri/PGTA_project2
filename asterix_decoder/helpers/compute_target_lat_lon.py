import math

# -----------------------------
# POSITION OF THE RADAR
# -----------------------------

LAT_RADAR = 41.30070234
LON_RADAR = 2.10205817
H_RADAR = 27.09296262


# -----------------------------
# C# GeodeticUtils.cs constants
# -----------------------------

A = 6378137.0
B = 6356752.3142
E2 = 0.00669437999013
NM2METERS = 1852.0
FT2METERS = 0.3048
DEG2RAD = math.pi / 180.0
RAD2DEG = 180.0 / math.pi
ALMOST_ZERO = 1e-10
REQUIRED_PRECISION = 1e-8

# -----------------------------
# Exact clone of GeoUtils.cs
# -----------------------------
def _calculate_earth_radius(self, lat_rad):
    # Radius of curvature in meridian
    return (self.A * (1.0 - self.E2)) / ((1.0 - self.E2 * (math.sin(lat_rad) ** 2.0)) ** 1.5)

def _calculate_elevation(self, center_height, R, rho_m, h_target):
    if rho_m < self.ALMOST_ZERO:
        return 0.0

    temp = (
        2.0 * R * (h_target - center_height)
        + h_target * h_target
        - center_height * center_height
        - rho_m * rho_m
    ) / (2.0 * rho_m * (R + center_height))

    if -1.0 < temp < 1.0:
        return math.asin(temp)
    else:
        return math.pi / 2.0

def _radar_spherical_to_radar_cartesian(self, rho_m, theta_rad, elevation_rad):
    x = rho_m * math.cos(elevation_rad) * math.sin(theta_rad)
    y = rho_m * math.cos(elevation_rad) * math.cos(theta_rad)
    z = rho_m * math.sin(elevation_rad)
    return x, y, z

def _calculate_rotation_matrix(lat_rad, lon_rad):
    return [
        [-math.sin(lon_rad),  math.cos(lon_rad), 0.0],
        [-(math.sin(lat_rad) * math.cos(lon_rad)),
        -(math.sin(lat_rad) * math.sin(lon_rad)),
        math.cos(lat_rad)],
        [ math.cos(lat_rad) * math.cos(lon_rad),
        math.cos(lat_rad) * math.sin(lon_rad),
        math.sin(lat_rad)]
    ]

def _calculate_translation_matrix(lat_rad, lon_rad, h_m):
    nu = A / math.sqrt(1.0 - E2 * (math.sin(lat_rad) ** 2.0))
    x = (nu + h_m) * math.cos(lat_rad) * math.cos(lon_rad)
    y = (nu + h_m) * math.cos(lat_rad) * math.sin(lon_rad)
    z = (nu * (1.0 - E2) + h_m) * math.sin(lat_rad)
    return x, y, z

def _matT_vec_mul(M, v):
    # M^T * v
    return (
        M[0][0]*v[0] + M[1][0]*v[1] + M[2][0]*v[2],
        M[0][1]*v[0] + M[1][1]*v[1] + M[2][1]*v[2],
        M[0][2]*v[0] + M[1][2]*v[1] + M[2][2]*v[2],
    )

def _radar_cartesian_to_geocentric(lat_rad, lon_rad, h_m, x, y, z):
    T = _calculate_translation_matrix(lat_rad, lon_rad, h_m)
    R = _calculate_rotation_matrix(lat_rad, lon_rad)
    rx, ry, rz = _matT_vec_mul(R, (x, y, z))   # R^T * v
    return (rx + T[0], ry + T[1], rz + T[2])

def _geocentric_to_geodesic(X, Y, Z):
    if abs(X) < ALMOST_ZERO and abs(Y) < ALMOST_ZERO:
        if abs(Z) < ALMOST_ZERO:
            lat = math.pi / 2.0
        else:
            lat = (math.pi / 2.0) * ((Z / abs(Z)) + 0.5)
        lon = 0.0
        h = abs(Z) - B
        return lat, lon, h

    d_xy = math.sqrt(X*X + Y*Y)

    lat = math.atan((Z / d_xy) / (1.0 - (A * E2) / math.sqrt(d_xy*d_xy + Z*Z)))
    nu = A / math.sqrt(1.0 - E2 * (math.sin(lat) ** 2.0))
    h = (d_xy / math.cos(lat)) - nu

    lat_prev = -0.1 if lat >= 0 else 0.1
    loops = 0

    while abs(lat - lat_prev) > REQUIRED_PRECISION and loops < 50:
        loops += 1
        lat_prev = lat
        lat = math.atan(
            (Z * (1.0 + h / nu)) /
            (d_xy * ((1.0 - E2) + (h / nu)))
        )
        nu = A / math.sqrt(1.0 - E2 * (math.sin(lat) ** 2.0))
        h = d_xy / math.cos(lat) - nu

    lon = math.atan2(Y, X)
    return lat, lon, h


def compute_target_lat_lon(rho_nm, theta_deg, FL):
    if FL is None:
        FL = 0
    lat_ref = LAT_RADAR * DEG2RAD
    lon_ref = LON_RADAR * DEG2RAD
    rho_m = rho_nm * NM2METERS
    theta_rad = theta_deg * DEG2RAD
    h_target_m = FL * 100.0 * FT2METERS  # Convert FL to meters
    R = _calculate_earth_radius(lat_ref)
    elev = _calculate_elevation(H_RADAR, R, rho_m, h_target_m)
    x, y, z = _radar_spherical_to_radar_cartesian(rho_m, theta_rad, elev)
    X, Y, Z = _radar_cartesian_to_geocentric(lat_ref, lon_ref, H_RADAR, x, y, z)
    lat_rad, lon_rad = _geocentric_to_geodesic(X, Y, Z)

    return round(lat_rad * RAD2DEG, 8), round(lon_rad * RAD2DEG, 8) #, h_out, elev * RAD2DEG