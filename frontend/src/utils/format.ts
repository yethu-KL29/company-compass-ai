interface Price {
  price_minor: number | null;
  currency: string;
  billing_period: string;
  billing_unit: string;
}

export function formatPrice(price: Price): string {
  if (price.price_minor === null) return "Contact for pricing";
  const formatter = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: price.currency,
  });
  const digits = formatter.resolvedOptions().maximumFractionDigits ?? 2;
  const amount = formatter.format(price.price_minor / 10 ** digits);
  return `${amount} / ${price.billing_unit} / ${price.billing_period}`;
}

export const readable = (value: string) =>
  value.replaceAll("_", " ").replaceAll("-", " ");

export function commaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
