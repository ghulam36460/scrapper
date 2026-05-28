from __future__ import annotations


class ComputerVisionLayer:
    """Computer vision adapter for business media, with face identification disabled."""

    def analyze_image_metadata(self, image_url: str, alt_text: str = "") -> dict[str, object]:
        lowered = " ".join([image_url, alt_text]).lower()
        labels = []
        for label in ["restaurant", "clinic", "office", "storefront", "logo", "menu", "vehicle", "building"]:
            if label in lowered:
                labels.append(label)
        return {
            "image_url": image_url,
            "object_labels": labels,
            "ocr_text": alt_text,
            "face_detection": False,
            "face_identification": False,
            "manual_review_required": bool("person" in lowered or "face" in lowered),
        }

    def state(self) -> dict[str, object]:
        return {
            "implemented": ["image_metadata_labels", "ocr_text_field_adapter"],
            "adapter_ready": ["object_detection", "logo_detection", "storefront_classification"],
            "disabled": ["face_identification", "biometric_recognition"],
            "safety_boundary": "No face recognition or identity matching. Business media only.",
        }
