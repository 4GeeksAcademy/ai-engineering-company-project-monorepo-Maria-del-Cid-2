import { OutboundFormPanel } from "@/components/inventory";

export default async function OutboundOrderPage({
  searchParams,
}: {
  searchParams: Promise<{ product?: string | string[] }>;
}) {
  const { product } = await searchParams;
  const productId = Array.isArray(product) ? product[0] : product;

  return <OutboundFormPanel initialProductId={productId ?? null} />;
}