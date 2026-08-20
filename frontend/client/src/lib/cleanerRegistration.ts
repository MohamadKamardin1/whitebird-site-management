export type IndividualCleanerRegistration = {
  first_name: string;
  last_name: string;
  id_number: string;
  birth_date: string;
};

export function isIndividualCleanerRegistrationReady(form: IndividualCleanerRegistration): boolean {
  return Boolean(form.first_name.trim() && form.last_name.trim() && form.id_number.trim() && form.birth_date);
}
