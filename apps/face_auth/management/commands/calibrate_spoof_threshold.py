"""
Management command: calibrate_spoof_threshold
----------------------------------------------
Runs the DeepFace Fasnet anti-spoofing model over two folders of images
(REAL face photos vs SPOOF images), prints score distributions for each,
and recommends an optimal FACE_SPOOF_THRESHOLD.

Usage:
    python manage.py calibrate_spoof_threshold \\
        --real /path/to/real_faces/ \\
        --spoof /path/to/spoof_images/

Folder format:
    Any common image file (*.jpg, *.jpeg, *.png, *.bmp, *.webp).
    Images do not need to contain a single face — the model processes the
    full image (enforce_detection=False).

Output (in Uzbek):
    - Score distribution per set (min / median / mean / max / std)
    - Count of images that DeepFace classified as real vs spoof
    - Overlap between real and spoof distributions
    - Recommended threshold (maximises F1 / Youden's J)
    - Suggested .env line

Notes:
    - Requires DeepFace and weights in ~/.deepface/weights/.
    - Run on representative images from your deployment environment
      (same camera, lighting conditions as production).
    - Re-run after changing camera hardware or environment.
"""
import glob
import pathlib
from django.core.management.base import BaseCommand


SUPPORTED_EXT = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


def _load_images_from_folder(folder: str) -> list:
    """Return list of (path, ndarray) for all images in folder."""
    import cv2
    folder_path = pathlib.Path(folder)
    if not folder_path.is_dir():
        raise ValueError(f"Papka topilmadi: {folder}")
    images = []
    for ext in SUPPORTED_EXT:
        for fpath in folder_path.glob(f'*{ext}'):
            img = cv2.imread(str(fpath))
            if img is not None:
                images.append((str(fpath), img))
        for fpath in folder_path.glob(f'*{ext.upper()}'):
            img = cv2.imread(str(fpath))
            if img is not None:
                images.append((str(fpath), img))
    return images


def _score_images(images: list) -> list:
    """Return list of (path, is_real, score) for each image."""
    from apps.face_auth.services.passive_liveness import _deepface_antispoof_result
    results = []
    for path, img in images:
        is_real, score = _deepface_antispoof_result(img)
        results.append((path, is_real, score))
    return results


def _distribution(scores: list) -> dict:
    """Compute basic statistics for a list of floats."""
    import numpy as np
    if not scores:
        return {'n': 0, 'min': None, 'max': None, 'mean': None, 'median': None, 'std': None}
    arr = sorted(scores)
    return {
        'n':      len(arr),
        'min':    min(arr),
        'max':    max(arr),
        'mean':   float(np.mean(arr)),
        'median': float(np.median(arr)),
        'std':    float(np.std(arr)),
    }


def _best_threshold(real_scores: list, spoof_scores: list) -> float:
    """
    Find threshold T that maximises Youden's J = sensitivity + specificity - 1.
    Sensitivity = TP/(TP+FN)  (fraction of real correctly accepted)
    Specificity = TN/(TN+FP)  (fraction of spoof correctly rejected)
    """
    import numpy as np
    if not real_scores or not spoof_scores:
        return 0.7
    all_scores = sorted(set(real_scores + spoof_scores))
    best_j, best_t = -1.0, 0.7
    for t in all_scores:
        tp = sum(1 for s in real_scores  if s >= t)
        fn = sum(1 for s in real_scores  if s <  t)
        tn = sum(1 for s in spoof_scores if s <  t)
        fp = sum(1 for s in spoof_scores if s >= t)
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        j = sensitivity + specificity - 1.0
        if j > best_j:
            best_j, best_t = j, t
    return round(best_t, 3)


def _overlap_pct(real_scores: list, spoof_scores: list) -> float:
    """Percentage of real scores that are below max(spoof) — crude overlap."""
    if not real_scores or not spoof_scores:
        return 0.0
    max_spoof = max(spoof_scores)
    overlapping = sum(1 for s in real_scores if s <= max_spoof)
    return 100.0 * overlapping / len(real_scores)


class Command(BaseCommand):
    help = "Fasnet anti-spoofing chegarasini kalibrlash (haqiqiy vs soxta rasmlar)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--real',
            required=True,
            metavar='PAPKA',
            help="Haqiqiy yuz rasmlari papkasi",
        )
        parser.add_argument(
            '--spoof',
            required=True,
            metavar='PAPKA',
            help="Soxta rasmlar papkasi (skrinshot, chop etilgan rasm, ekrandagi video)",
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            default=False,
            help="Har bir rasm uchun ballarni ko'rsatish",
        )

    def handle(self, *args, **options):
        real_folder  = options['real']
        spoof_folder = options['spoof']
        verbose      = options['verbose']

        self.stdout.write(self.style.HTTP_INFO("\n═══ FASNET ANTI-SPOOFING KALIBRLASH ═══\n"))

        # Load images
        self.stdout.write("Rasmlar yuklanmoqda...")
        try:
            real_imgs  = _load_images_from_folder(real_folder)
            spoof_imgs = _load_images_from_folder(spoof_folder)
        except ValueError as e:
            self.stdout.write(self.style.ERROR(str(e)))
            return

        if not real_imgs:
            self.stdout.write(self.style.ERROR(
                f"Haqiqiy rasmlar papkasida rasm topilmadi: {real_folder}"
            ))
            return
        if not spoof_imgs:
            self.stdout.write(self.style.ERROR(
                f"Soxta rasmlar papkasida rasm topilmadi: {spoof_folder}"
            ))
            return

        self.stdout.write(
            f"  Haqiqiy rasmlar: {len(real_imgs)} ta   "
            f"Soxta rasmlar: {len(spoof_imgs)} ta\n"
        )

        # Score images
        self.stdout.write("Fasnet modeli ishlatilmoqda (biroz vaqt ketishi mumkin)...")
        try:
            real_results  = _score_images(real_imgs)
            spoof_results = _score_images(spoof_imgs)
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Model xatosi: {exc}"))
            return

        real_scores  = [s for _, _, s in real_results  if s >= 0]
        spoof_scores = [s for _, _, s in spoof_results if s >= 0]

        real_real_count  = sum(1 for _, ir, _ in real_results  if ir is True)
        spoof_real_count = sum(1 for _, ir, _ in spoof_results if ir is True)

        # Print verbose per-file scores
        if verbose:
            self.stdout.write("\n--- HAQIQIY RASMLAR ---")
            for path, is_real, score in real_results:
                flag = "✓" if is_real else "✗"
                self.stdout.write(f"  {flag} {pathlib.Path(path).name:<30} ball={score:.3f}")
            self.stdout.write("\n--- SOXTA RASMLAR ---")
            for path, is_real, score in spoof_results:
                flag = "✓" if is_real else "✗"
                self.stdout.write(f"  {flag} {pathlib.Path(path).name:<30} ball={score:.3f}")

        # Print distributions
        rd = _distribution(real_scores)
        sd = _distribution(spoof_scores)

        self.stdout.write(self.style.SUCCESS("\n═══ BAL TAQSIMOTI ═══"))
        self.stdout.write(
            f"\n{'':4}{'Ko\'rsatkich':<20} {'Haqiqiy':>10} {'Soxta':>10}"
        )
        self.stdout.write("-" * 46)
        for key, label in [
            ('n',      "Rasm soni"),
            ('min',    "Minimal"),
            ('max',    "Maksimal"),
            ('mean',   "O'rtacha"),
            ('median', "Mediana"),
            ('std',    "Standart og'ish"),
        ]:
            rv = rd[key]
            sv = sd[key]
            rstr = f"{rv:.3f}" if isinstance(rv, float) else str(rv)
            sstr = f"{sv:.3f}" if isinstance(sv, float) else str(sv)
            self.stdout.write(f"{'':4}{label:<20} {rstr:>10} {sstr:>10}")

        # Classification accuracy
        self.stdout.write(f"\n{'':4}{'is_real=True':<20} {real_real_count:>10}/{rd['n']} {spoof_real_count:>10}/{sd['n']}")

        # Overlap
        overlap = _overlap_pct(real_scores, spoof_scores)
        self.stdout.write(f"\n  Haqiqiy rasmlar ichida soxta bilan ustma-ust tushish: {overlap:.1f}%")
        if overlap > 10:
            self.stdout.write(self.style.WARNING(
                "  ⚠ Katta ustma-ust tushish aniqlandi. Rasmlar sifatini tekshiring."
            ))

        # Recommendation
        best_t = _best_threshold(real_scores, spoof_scores)
        self.stdout.write(self.style.SUCCESS(f"\n═══ TAVSIYA ═══"))
        self.stdout.write(f"\n  Optimal chegara: {best_t}")
        self.stdout.write(f"  .env fayliga qo'shing:")
        self.stdout.write(self.style.WARNING(f"    FACE_SPOOF_THRESHOLD={best_t}"))

        # Safety check
        current = float(__import__('django').conf.settings.__dict__.get(
            '_wrapped', type('', (), {'FACE_SPOOF_THRESHOLD': 0.7})()
        ).__dict__.get('FACE_SPOOF_THRESHOLD', 0.7))
        if best_t < 0.5:
            self.stdout.write(self.style.ERROR(
                "\n  DIQQAT: Tavsiya etilgan chegara juda past (<0.5)! "
                "Soxta rasmlar sifatini yoki model holatini tekshiring."
            ))
        elif best_t > 0.95:
            self.stdout.write(self.style.WARNING(
                "\n  Diqqat: Chegara juda baland (>0.95) — haqiqiy foydalanuvchilar "
                "rad etilishi mumkin. Ko'proq rasmlar bilan qayta sinab ko'ring."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\n  Bu chegara ishonchli ko'rinadi."
            ))

        self.stdout.write(
            "\n  ESLATMA: Kalibratsiya uchun kamida 20-30 ta haqiqiy va soxta rasm "
            "ishlatish tavsiya etiladi. Hozir ishlatilgan: "
            f"{rd['n']} haqiqiy, {sd['n']} soxta.\n"
        )
