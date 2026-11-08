import { describe, expect, it } from "vitest";
import { tokenizeSql } from "@/lib/sql-highlight";
import { FIX } from "./fixtures";

describe("tokenizeSql", () => {
  it("is lossless: joining tokens reproduces the SQL", () => {
    const sql = FIX.verified.sql!.text;
    expect(tokenizeSql(sql).map((t) => t.value).join("")).toBe(sql);
  });
  it("classifies keywords, params, comments, strings and numbers", () => {
    const toks = tokenizeSql("SELECT SUM(x) -- hi\nWHERE a = CAST(? AS VARCHAR(16)) AND b = 'it''s' AND c > 10.5");
    const by = (type: string) => toks.filter((t) => t.type === type).map((t) => t.value);
    expect(by("keyword")).toEqual(expect.arrayContaining(["SELECT", "WHERE", "AS", "AND"]));
    expect(by("func")).toEqual(expect.arrayContaining(["SUM", "CAST"]));
    expect(by("param")).toEqual(["?"]);
    expect(by("comment")).toEqual(["-- hi"]);
    expect(by("string")).toEqual(["'it''s'"]);
    expect(by("number")).toEqual(expect.arrayContaining(["16", "10.5"]));
    expect(by("type")).toContain("VARCHAR");
  });
});
