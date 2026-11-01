// Phone photos are often larger than the backend's 5 MB limit; 2000 px is plenty for Textract to read a page.
export async function shrink(file: File, longestSide = 2000): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, longestSide / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("Could not read the photo"))), "image/jpeg", 0.85),
  );
}

// "4.50" -> 450; "" -> null (nothing typed); anything else -> NaN. Whole cents, no floats.
export function typedCents(text: string): number | null {
  const found = text.trim().replace(/^\$/, "").match(/^(\d{0,7})(?:\.(\d{1,2}))?$/);
  if (!text.trim()) return null;
  if (!found || (!found[1] && !found[2])) return NaN;
  return Number(found[1] || 0) * 100 + Number((found[2] ?? "").padEnd(2, "0"));
}
