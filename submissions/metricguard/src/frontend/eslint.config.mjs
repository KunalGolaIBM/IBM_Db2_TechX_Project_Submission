import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const config = [
  ...nextVitals,
  ...nextTs,
  { ignores: [".next/**", "node_modules/**", "lib/api/schema.d.ts", "next-env.d.ts", "playwright-report/**", "test-results/**"] },
];
export default config;
