/** Repository-owned White Bird visual assets; base-aware for Vite dev and Django static production paths. */
const asset = (file: string) => `${import.meta.env.BASE_URL}assets/${file}`;
export const brandMark = asset("whitebird-mark.png");
export const brandLogo = asset("whitebird-logo.png");
export const siteIcon = asset("apple-icon.png");
export const coastalContours = asset("whitebird-coastal-contours.png");
export const loginOperationsImage = asset("whitebird-login-operations.png");
export const privateFilesImage = asset("whitebird-private-files.png");
export const reportsArchiveImage = asset("whitebird-reports-archive.png");
