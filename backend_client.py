import requests
from datetime import datetime
from config import API_URL, CAMERA_NAME, LOCATION
from memory import worker_presence
from violations import get_worker_event_history, is_repeat_offender, open_events


def build_payload(report, workers, transitions=None):
    """
    Convert YOLO report + worker information into backend JSON format.

    transitions: list of (event, transition_str) tuples for violation
    events that opened/resolved since the last send (see violations.py
    and live_detection.py's pending_transitions). Optional -- omit or
    pass [] for a payload with no event data (e.g. a pure heartbeat).
    """

    transitions = transitions or []

    findings = []

    # ==========================================
    # PPE Findings
    # ==========================================
    if report["helmet_violation"] > 0:
        findings.append({
            "category": "PPE",
            "finding": "Helmet Missing",
            "severity": "High",
            "confidence": 0.95,
            "count": report["helmet_violation"]
        })

    if report["vest_violation"] > 0:
        findings.append({
            "category": "PPE",
            "finding": "Safety Vest Missing",
            "severity": "High",
            "confidence": 0.94,
            "count": report["vest_violation"]
        })

    if report["mask_violation"] > 0:
        findings.append({
            "category": "PPE",
            "finding": "Mask Missing",
            "severity": "Medium",
            "confidence": 0.92,
            "count": report["mask_violation"]
        })

    # ==========================================
    # Site Safety
    # ==========================================
    if report["vehicle"] > 0:
        findings.append({
            "category": "Site Safety",
            "finding": "Construction Vehicle Present",
            "severity": "Low",
            "confidence": 0.96,
            "count": report["vehicle"]
        })

    if report["machinery"] > 0:
        findings.append({
            "category": "Site Safety",
            "finding": "Heavy Machinery Operating",
            "severity": "Medium",
            "confidence": 0.96,
            "count": report["machinery"]
        })

    if report["safety_cone"] == 0:
        findings.append({
            "category": "Site Safety",
            "finding": "Safety Cone Missing",
            "severity": "Medium",
            "confidence": 0.90,
            "count": 1
        })

    # ==========================================
    # Worker-wise Data
    #
    # total_violation_events / repeat_offender / evidence_history are
    # now derived from actual violation EVENTS (see violations.py),
    # not a frame counter -- e.g. total_violation_events: 3 means this
    # worker has had 3 distinct violation incidents, not that they
    # were in violation for 3 frames.
    # ==========================================
    worker_data = []

    for worker_id, info in workers.items():

        presence = worker_presence.get(worker_id, {})
        event_history = get_worker_event_history(worker_id)
        open_event = open_events.get(worker_id)

        worker_data.append({

            "worker_id": worker_id,

            "bbox": info["bbox"],

            "helmet": info["helmet"],

            "vest": info["vest"],

            "mask": info["mask"],

            "violations": info["violations"],

            # How many distinct PPE items THIS worker is missing right
            # now (0-3) -- e.g. worker A: 3 violations, worker B: 1.
            "violation_count": len(info["violations"]),

            # Evidence photo for their currently open incident, if any.
            "image": info.get("image", None),

            "first_seen": presence.get("first_seen"),

            "last_seen": presence.get("last_seen"),

            # Duration of the CURRENTLY open violation event (0 if
            # they're compliant right now).
            "violation_duration_seconds": open_event["duration_seconds"] if open_event else 0,

            # Count of distinct violation INCIDENTS (open + resolved),
            # not frames.
            "total_violation_events": len(event_history),

            "repeat_offender": is_repeat_offender(worker_id),

            "evidence_history": [
                e["evidence_image"] for e in event_history if e["evidence_image"]
            ]

        })

    # ==========================================
    # Violation Events
    #
    # Only the events that actually transitioned (opened or resolved)
    # since the last send -- this is the real "what happened" log,
    # separate from the live worker snapshot above.
    # ==========================================
    event_data = [
        {
            "event_id": event["event_id"],
            "worker_id": event["worker_id"],
            "transition": transition,
            "violations": event["violations"],
            "start_time": event["start_time"],
            "end_time": event["end_time"],
            "status": event["status"],
            "duration_seconds": event["duration_seconds"],
            "evidence_image": event["evidence_image"]
        }
        for event, transition in transitions
    ]

    # ==========================================
    # Final Payload
    # ==========================================
    payload = {

        "camera_name": CAMERA_NAME,

        "location": LOCATION,

        "timestamp": datetime.now().isoformat(),

        "workers_detected": report["workers"],

        "overall_compliance": report["overall_compliance"],

        "findings": findings,

        "workers": worker_data,

        "events": event_data

    }

    return payload


def send_to_backend(report, workers, transitions=None):
    """
    Send payload to FastAPI backend.
    """

    payload = build_payload(report, workers, transitions)

    # ==========================================
    # Print JSON
    # ==========================================
    print("\n================ JSON PAYLOAD ================\n")

    print(payload)

    print("\n==============================================\n")

    try:

        response = requests.post(
            API_URL,
            json=payload,
            timeout=5
        )

        print(f"Backend Response Code : {response.status_code}")

        try:

            print("Backend Response :", response.json())

        except Exception:

            print("Backend Response Text :", response.text)

    except requests.exceptions.ConnectionError:

        print("\nBackend Connection Failed!")

        print("FastAPI server is probably not running.")

        print(f"Expected URL : {API_URL}\n")

    except Exception as e:

        print("\nUnexpected Error")

        print(e)