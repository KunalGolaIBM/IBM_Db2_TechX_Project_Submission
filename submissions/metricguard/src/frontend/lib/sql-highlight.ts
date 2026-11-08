/** Tiny dependency-free SQL tokenizer for display (Db2 dialect subset used by the compiler). */

export type SqlTokenType = "keyword" | "string" | "number" | "comment" | "param" | "type" | "func" | "text";
export interface SqlToken { type: SqlTokenType; value: string }

const KEYWORDS = new Set([
  "WITH", "AS", "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "JOIN", "LEFT", "INNER", "ON", "GROUP", "BY", "ORDER",
  "ASC", "DESC", "FETCH", "FIRST", "ROWS", "ROW", "ONLY", "DISTINCT", "CASE", "WHEN", "THEN", "ELSE", "END", "NULL", "IS",
  "BETWEEN", "LIKE", "HAVING", "UNION", "ALL", "OVER", "PARTITION",
]);
const TYPES = new Set(["VARCHAR", "TIMESTAMP", "DECIMAL", "INTEGER", "INT", "BIGINT", "DATE", "DOUBLE", "CHAR"]);
const FUNCS = new Set(["SUM", "COUNT", "COALESCE", "CAST", "VARCHAR_FORMAT", "NULLIF", "AVG", "MIN", "MAX", "DECIMAL", "ROUND"]);

const RE = /(--[^\n]*)|('(?:[^']|'')*')|(\b\d+(?:\.\d+)?\b)|(\?)|([A-Za-z_][A-Za-z0-9_]*)|(\s+)|([\s\S])/g;

export function tokenizeSql(sql: string): SqlToken[] {
  const out: SqlToken[] = [];
  const push = (type: SqlTokenType, value: string) => {
    const last = out[out.length - 1];
    if (last && last.type === type && type === "text") last.value += value;
    else out.push({ type, value });
  };
  for (const m of sql.matchAll(RE)) {
    const [text, comment, str, num, param, word] = m;
    if (comment) push("comment", text);
    else if (str) push("string", text);
    else if (num) push("number", text);
    else if (param) push("param", text);
    else if (word) {
      const up = word.toUpperCase();
      // `DECIMAL(` / `VARCHAR(` after CAST ... AS is a type; function names are followed by "(".
      const after = sql.slice((m.index ?? 0) + text.length);
      const isCall = /^\s*\(/.test(after);
      if (KEYWORDS.has(up)) push("keyword", text);
      else if (TYPES.has(up) && !(FUNCS.has(up) && isCall && up !== "DECIMAL")) push("type", text);
      else if (FUNCS.has(up) && isCall) push("func", text);
      else push("text", text);
    } else push("text", text);
  }
  return out;
}
