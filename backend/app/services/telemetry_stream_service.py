"""Telemetry stream service — gap detection and 10Hz linear interpolation."""

from backend.app.core.logging import get_logger

logger = get_logger(__name__)


def interpolate_telemetry(points: list, target_hz: int = 10) -> list[dict]:
    """Sorts, detects gaps, and resamples telemetry points to 10Hz."""
    if not points:
        return []

    # 1. Chronological ordering
    points = sorted(points, key=lambda p: p.time_ms)
    t_min = points[0].time_ms
    t_max = points[-1].time_ms

    step_ms = 1000 // target_hz  # 100ms for 10Hz
    start_t = ((t_min + step_ms - 1) // step_ms) * step_ms

    # 2. Gap detection
    for i in range(len(points) - 1):
        gap = points[i + 1].time_ms - points[i].time_ms
        if gap > 2000:
            logger.warning(
                "Telemetry gap of %d ms detected between %d ms and %d ms",
                gap, points[i].time_ms, points[i + 1].time_ms
            )

    # 3. Interpolation/Resampling loop
    interpolated = []
    idx = 0
    num_points = len(points)

    current_t = start_t
    while current_t <= t_max:
        # Advance points pointer until points[idx+1].time_ms >= current_t
        while idx < num_points - 1 and points[idx + 1].time_ms < current_t:
            idx += 1

        p_curr = points[idx]
        if idx < num_points - 1:
            p_next = points[idx + 1]
            t_curr = p_curr.time_ms
            t_next = p_next.time_ms

            if t_next == t_curr:
                alpha = 0.0
            else:
                alpha = (current_t - t_curr) / (t_next - t_curr)

            # Linear interpolation for continuous channels
            d_curr = p_curr.speed_kmh
            speed = d_curr + alpha * (p_next.speed_kmh - d_curr)
            rpm = int(p_curr.rpm + alpha * (p_next.rpm - p_curr.rpm))

            pct_curr = p_curr.throttle_pct
            throttle = pct_curr + alpha * (p_next.throttle_pct - pct_curr)

            dist_curr = p_curr.distance_m
            distance = dist_curr + alpha * (p_next.distance_m - dist_curr)

            # Discrete and binary fields nearest-neighbor mapping
            gear = p_curr.gear if alpha < 0.5 else p_next.gear
            brake = p_curr.brake if alpha < 0.5 else p_next.brake
            drs = p_curr.drs if alpha < 0.5 else p_next.drs

            x = (p_curr.x + alpha * (p_next.x - p_curr.x)) if (
                p_curr.x is not None and p_next.x is not None
            ) else None
            y = (p_curr.y + alpha * (p_next.y - p_curr.y)) if (
                p_curr.y is not None and p_next.y is not None
            ) else None
            z = (p_curr.z + alpha * (p_next.z - p_curr.z)) if (
                p_curr.z is not None and p_next.z is not None
            ) else None
        else:
            # Last point mapping
            speed = p_curr.speed_kmh
            rpm = p_curr.rpm
            gear = p_curr.gear
            throttle = p_curr.throttle_pct
            brake = p_curr.brake
            drs = p_curr.drs
            x = p_curr.x
            y = p_curr.y
            z = p_curr.z
            distance = p_curr.distance_m

        interpolated.append({
            "time_ms": current_t,
            "speed": round(speed, 2),
            "throttle": round(throttle, 2),
            "brake": bool(brake),
            "gear": int(gear) if gear is not None else 0,
            "rpm": int(rpm) if rpm is not None else 0,
            "drs": bool(drs),
            "position": {
                "x": round(x, 2),
                "y": round(y, 2),
                "z": round(z, 2)
            } if (x is not None and y is not None and z is not None) else None,
            "distance_m": round(distance, 2)
        })

        current_t += step_ms

    return interpolated
