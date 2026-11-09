/**
 * Genuine LangChain integration for CarbonNova (eligible framework).
 * Uses LangChain chat models/prompts to generate grounded explanations.
 * AI output is assistive, not certification or scientific measurement.
 */
import { ChatOpenAI } from '@langchain/openai';
import { ChatPromptTemplate } from '@langchain/core/prompts';
import { StringOutputParser } from '@langchain/core/output_parsers';

function getModel() {
  const apiKey = process.env.NEBIUS_API_KEY || process.env.AI_API_KEY || process.env.OPENAI_API_KEY;
  if (!apiKey) return null;
  const baseURL = process.env.NEBIUS_BASE_URL || process.env.AI_BASE_URL || 'https://api.tokenfactory.nebius.com/v1/';
  const model = process.env.NEBIUS_MODEL || process.env.AI_MODEL || 'nvidia/Nemotron-3_5-Lightning';
  return new ChatOpenAI({ apiKey, configuration: { baseURL }, model, temperature: 0.2, maxTokens: 700 });
}

export async function explainAssessmentWithLangChain({ land, assessment, project }) {
  const model = getModel();
  if (!model) return { ok: false, error: 'AI/LangChain model is not configured. Set NEBIUS_API_KEY or AI_API_KEY.' };
  const prompt = ChatPromptTemplate.fromMessages([
    ['system', 'You are CarbonNova\'s evidence assistant. Use only the provided context from the application database/records. Clearly label estimates, assumptions, and missing evidence. Never claim certified carbon credits, independent verification, or fabricated measurements. Keep the explanation practical and factual.'],
    ['human', 'Context (from CarbonNova records):\n{context}\n\nTask: {task}'],
  ]);
  const chain = prompt.pipe(model).pipe(new StringOutputParser());
  const context = JSON.stringify({ land, assessment, project }, null, 2).slice(0, 12000);
  const answer = await chain.invoke({ context, task: 'Explain the land/carbon assessment in simple language, list evidence gaps, and give 3 grounded recommendations.' });
  return { ok: true, framework: 'LangChain', answer, disclaimer: 'AI-assisted explanation generated via LangChain; not certification, validation, or a scientific measurement.' };
}

export async function reviewDocumentsWithLangChain({ project, documents, findings }) {
  const model = getModel();
  if (!model) return { ok: false, error: 'AI/LangChain model is not configured.' };
  const prompt = ChatPromptTemplate.fromMessages([
    ['system', 'You assist with carbon-project document consistency review for a demo platform. You are not an official certifier. Identify missing documents, inconsistencies, unsupported claims, and risks based only on provided metadata. Be cautious and factual.'],
    ['human', 'Project metadata:\n{project}\n\nDocuments metadata:\n{documents}\n\nHeuristic findings:\n{findings}\n\nProvide a concise review summary.'],
  ]);
  const chain = prompt.pipe(model).pipe(new StringOutputParser());
  const answer = await chain.invoke({ project: JSON.stringify(project).slice(0,6000), documents: JSON.stringify(documents).slice(0,6000), findings: JSON.stringify(findings).slice(0,4000) });
  return { ok: true, framework: 'LangChain', answer, disclaimer: 'AI-assisted document review via LangChain; not official certification.' };
}
