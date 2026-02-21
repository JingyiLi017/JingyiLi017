import { BrowserWindow, app } from "electron";
import fs from "node:fs/promises";
import path from "node:path";

function safeName(input: string) {
  return input
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 120);
}

export type ExportPdfInput = {
  html: string;
  fileStem: string;
};

export async function exportHtmlToPdf({ html, fileStem }: ExportPdfInput): Promise<string> {
  if (!html || !html.trim()) {
    throw new Error("EMPTY_HTML");
  }

  const win = new BrowserWindow({
    show: false,
    webPreferences: {
      sandbox: true,
      contextIsolation: true,
      javascript: false
    }
  });

  try {
    const dataUrl = `data:text/html;charset=utf-8,${encodeURIComponent(html)}`;
    await win.loadURL(dataUrl);

    await win.webContents.executeJavaScript(
      `(async()=>{if(document.fonts&&document.fonts.ready){await document.fonts.ready;} return true;})()`
    );

    const pdfBuffer = await win.webContents.printToPDF({
      pageSize: "A4",
      printBackground: true,
      margins: { top: 0.6, bottom: 0.6, left: 0.6, right: 0.6 },
      landscape: false,
      preferCSSPageSize: true
    });

    const outDir = path.join(app.getPath("documents"), "NovelEngine", "Reports");
    await fs.mkdir(outDir, { recursive: true });

    const outputPath = path.join(outDir, `${safeName(fileStem || "chapter-report")}.pdf`);
    await fs.writeFile(outputPath, pdfBuffer);
    return outputPath;
  } finally {
    if (!win.isDestroyed()) {
      win.destroy();
    }
  }
}

