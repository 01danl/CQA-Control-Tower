/**
 * JSDoc boundary for docs/02_API_CONTRACT.md v1. No generated TS or duplicated
 * business rules. Backend owns scores, validation, versions and evidence.
 * See ../CONTRACTS.md for endpoint coverage and unavailable metadata.
 *
 * @typedef {'queued'|'running'|'completed'|'failed'} EvaluationStatus
 * @typedef {'client'|'operator'|'bot'|'system'} Speaker
 * @typedef {{message_index:number,timestamp:string,speaker:Speaker,text:string}} Message
 * @typedef {{group_id:string,conversation_id:string,language:string,channel:string,
 * message_count:number,latest_evaluation_id:?string,latest_score:?number}} ConversationSummary
 * @typedef {{group_id:string,conversation_id:string,language:string,channel:string,
 * audio_url:?string,transcript:Message[]}} ConversationDetail
 * @typedef {{id:string,name:string,section:string,description:string,instructions:string,
 * weight:number,type:'binary'|'numeric_scale'|'violation',allowed_values:(string|number)[],
 * allows_na:boolean,na_rule:string}} Criterion
 * @typedef {{name:string,criteria:Criterion[]}} RubricDraft
 * @typedef {RubricDraft & {rubric_id:string,version:number,created_at:string}} RubricDetail
 * @typedef {{message_index:number,timestamp:string,speaker:Speaker,quote:string,
 * kind:'support'|'expected_missing'}} Evidence
 * @typedef {{criterion_id:string,value:string|number,weighted_points:?number,reason:string,
 * evidence:Evidence[],review_flag:boolean,na_reason:?string,review_override:?Object}} CriterionResult
 * @typedef {{model:?string,input_tokens:?number,output_tokens:?number,
 * estimated_cost_usd:?number}} Usage
 * @typedef {{evaluation_id:string,group_id:string,conversation_id:string,rubric_id:string,
 * rubric_version:number,status:EvaluationStatus,created_at:string,original_score:?number,
 * final_score:?number,gross_error:boolean,needs_human_review:boolean,
 * results:CriterionResult[],usage:?Usage,error:?{code:string,message:string,details:?Object},
 * rubric_snapshot:RubricDetail}} EvaluationDetail
 * @typedef {{evaluation_id:string,status:EvaluationStatus}} EvaluationReceipt
 * @typedef {{group_id:string,total:number,imported:number,updated:number,skipped:number}} ImportResult
 * @typedef {{batch_id:string,status:EvaluationStatus,total:number,completed:number,
 * failed:number,pending:number}} BatchProgress
 * @typedef {{evaluation_id:string,criterion_id:string,comment:string}} AppealDraft
 * @typedef {AppealDraft & {appeal_id:string,status:string,created_at:string,
 * decision:?'uphold'|'override',new_value:?(number|string),reason:?string,final_score:?number}} AppealDetail
 * @typedef {{error:{code:string,message:string,details:?(Object|Array)}}} ErrorEnvelope
 */
export {};
