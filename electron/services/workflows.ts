import { callLlm } from "./llm";
import { AppConfig, BookTaskInput, BookTaskOutput, WritingTaskInput, WritingTaskOutput } from "./types";

export async function runWritingWorkflow(input: WritingTaskInput, config: AppConfig): Promise<WritingTaskOutput> {
  const plannerSystem = "你是资深内容策略师，输出必须结构化、可执行、避免空话。";
  const planPrompt = [
    `主题: ${input.topic}`,
    `受众: ${input.audience}`,
    `风格: ${input.style}`,
    `目标: ${input.objective}`,
    `约束: ${input.constraints || "无"}`,
    `素材: ${input.sourceMaterial || "无"}`,
    "请先输出一份高质量写作大纲，包含标题候选、段落目标、论据与案例建议。"
  ].join("\n");

  const outline = await callLlm(config, [
    { role: "system", content: plannerSystem },
    { role: "user", content: planPrompt }
  ]);

  const draft = await callLlm(config, [
    { role: "system", content: "你是专业作者，擅长按大纲产出完整成稿。" },
    {
      role: "user",
      content: `根据以下大纲写完整文章，确保逻辑连贯和细节具体：\n\n${outline}\n\n请输出可直接发布的初稿。`
    }
  ]);

  const refined = await callLlm(config, [
    { role: "system", content: "你是严格编辑，擅长提升说服力、节奏和可读性。" },
    {
      role: "user",
      content: `请润色下面初稿，并给出“最终版正文”：\n\n${draft}\n\n要求保留原意，增强标题、小结和行动号召。`
    }
  ]);

  return { outline, draft, refined };
}

export async function runBookDeconstruction(input: BookTaskInput, config: AppConfig): Promise<BookTaskOutput> {
  const summary = await callLlm(config, [
    { role: "system", content: "你是拆书教练。输出聚焦核心观点与关键证据。" },
    {
      role: "user",
      content: `书名: ${input.title}\n目标: ${input.businessGoal}\n内容:\n${input.content}\n\n请提炼核心摘要(300-500字)。`
    }
  ]);

  const frameworkMap = await callLlm(config, [
    { role: "system", content: "你是方法论专家，擅长抽象框架与因果链。" },
    {
      role: "user",
      content: `基于这份摘要，输出框架图谱(文本形式)，包含: 核心概念、关系、应用边界。\n\n${summary}`
    }
  ]);

  const actionPlan = await callLlm(config, [
    { role: "system", content: "你是执行教练，擅长把理念变成可度量行动。" },
    {
      role: "user",
      content: `基于摘要和框架，给出30天行动计划，按周拆分，并设置指标。\n\n摘要:\n${summary}\n\n框架:\n${frameworkMap}`
    }
  ]);

  const writingIdeas = await callLlm(config, [
    { role: "system", content: "你是内容运营策略师，擅长选题矩阵。" },
    {
      role: "user",
      content: `请把拆书结果映射成10个可写作选题，每个含标题、受众、观点、开头钩子。\n\n${summary}\n\n${frameworkMap}\n\n${actionPlan}`
    }
  ]);

  return { summary, frameworkMap, actionPlan, writingIdeas };
}
