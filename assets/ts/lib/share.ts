import { Toast } from "./toast";

export interface ShareData {
  title: string;
  text?: string;
  url?: string;
}

export class Share {
  /** Opens the system share sheet; without one, copies to the clipboard and confirms with a toast. */
  public static share(data: ShareData, copiedMessage: string): void {
    if (navigator.share) {
      navigator.share(data).catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          Toast.error(error);
        }
      });
      return;
    }
    const copy = [data.text, data.url].filter(Boolean).join("\n");
    navigator.clipboard
      .writeText(copy)
      .then(() => Toast.show(copiedMessage))
      .catch(Toast.error);
  }
}
