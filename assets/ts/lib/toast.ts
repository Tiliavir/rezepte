export class Toast {
  public static show(message: string): void {
    document.querySelector(".toast")?.remove();
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.setAttribute("role", "status");
    toast.textContent = message;
    toast.addEventListener("animationend", () => toast.remove());
    document.body.append(toast);
  }

  public static error(error: unknown): void {
    console.error(error);
    Toast.show(error instanceof Error ? error.message : String(error));
  }
}
