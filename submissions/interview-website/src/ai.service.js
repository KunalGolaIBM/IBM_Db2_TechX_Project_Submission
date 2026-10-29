const { GoogleGenAI } = require("@google/genai")
const { z } = require("zod")
const { zodToJsonSchema } = require("zod-to-json-schema")
const puppeteer = require("puppeteer")

const ai = new GoogleGenAI({
  apiKey: process.env.GOOGLE_GENAI_API_KEY,
})

const interviewReportSchema = z.object({
  matchScore: z.number().describe("A score between 0 and 100 indicating how well the candidate matches the role."),
  technicalQuestions: z.array(z.object({
    question: z.string(),
    intention: z.string(),
    answer: z.string(),
  })),
  behavioralQuestions: z.array(z.object({
    question: z.string(),
    intention: z.string(),
    answer: z.string(),
  })),
  skillGaps: z.array(z.object({
    skill: z.string(),
    severity: z.enum(["low", "medium", "high"]),
  })),
  preparationPlan: z.array(z.object({
    day: z.number(),
    focus: z.string(),
    tasks: z.array(z.string()),
  })),
  title: z.string(),
})

async function generateInterviewReport({ resume, selfDescription, jobDescription }) {
  const prompt = `Generate an interview report for a candidate with the following details:\nResume: ${resume}\nSelf Description: ${selfDescription}\nJob Description: ${jobDescription}`

  const response = await ai.models.generateContent({
    model: "gemini-2.5-flash-lite",
    contents: prompt,
    config: {
      responseMimeType: "application/json",
      responseSchema: zodToJsonSchema(interviewReportSchema),
    },
  })

  return JSON.parse(response.text)
}

async function generatePdfFromHtml(htmlContent) {
  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  })

  const page = await browser.newPage()
  await page.setContent(htmlContent, { waitUntil: "networkidle0" })

  const pdfBuffer = await page.pdf({
    format: "A4",
    margin: { top: "20mm", bottom: "20mm", left: "15mm", right: "15mm" },
  })

  await browser.close()
  return pdfBuffer
}

module.exports = { generateInterviewReport, generatePdfFromHtml }
