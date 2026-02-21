export interface AppConfig {
  endpoint: string;
  apiKey: string;
  model: string;
  temperature: number;
  mockMode?: boolean;
}

export interface WritingTaskInput {
  topic: string;
  audience: string;
  style: string;
  objective: string;
  constraints: string;
  sourceMaterial?: string;
}

export interface WritingTaskOutput {
  outline: string;
  draft: string;
  refined: string;
}

export interface BookTaskInput {
  title: string;
  content: string;
  businessGoal: string;
}

export interface BookTaskOutput {
  summary: string;
  frameworkMap: string;
  actionPlan: string;
  writingIdeas: string;
}
