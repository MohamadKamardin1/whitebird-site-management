export type CleanlinessTemplateLike = { is_active?: boolean; description?: string };

export function preferredCleanlinessTemplates<T extends CleanlinessTemplateLike>(templates: T[]): T[] {
  const configured = templates.filter((template) => template.is_active !== false);
  const official = configured.filter((template) => (template.description || "").startsWith("PDF-derived daily cleanliness worksheet"));
  return official.length ? official : configured;
}
