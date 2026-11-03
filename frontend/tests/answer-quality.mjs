// Existing esbuild dependency compiles the actual components; no test packages/downloads.
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const result = await build({
  stdin: { resolveDir: fileURLToPath(new URL('../', import.meta.url)), loader: 'tsx', contents: `
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import AnswerDocument from './src/components/AnswerDocument';
import AssistantTurn from './src/components/AssistantTurn';
import QuestionSuggestions from './src/components/QuestionSuggestions';
import { derivePanelState } from './src/panelState';
import { parseLine, citedNumbers, stripCites, sqlChart } from './src/answer';
const marks = parseLine('Evidence [1, 3][2].').filter(x=>x.kind==='cite').map(x=>x.n);
assert.deepEqual(marks,[1,3,2]);
assert.deepEqual(citedNumbers('Evidence [1, 3][2].'),[1,3,2]);
assert.equal(stripCites('A [1, 3]\\nB [2]'),'A \\nB');
const markdown = '# Findings\\n\\n**Charging** fails [1, 3].\\n\\n- First example [1]\\n- Another *example* [3]\\n\\n| Issue | Evidence |\\n| --- | --- |\\n| Battery | [1, 3] |';
const html=renderToStaticMarkup(<AnswerDocument text={markdown} validCitations={[1,3]} onCiteClick={()=>{}}/>);
assert(html.includes('<h2>Findings</h2>') && html.includes('<strong>Charging</strong>'));
assert(html.includes('<ul>') && html.includes('<table>') && html.includes('<em>example</em>'));
assert(!html.includes('**') && !html.includes('[1, 3]'));
assert(html.includes('Show evidence 1') && html.includes('Show evidence 3'));
const hostile=renderToStaticMarkup(<AnswerDocument text={'<script>alert(1)</script> [link](javascript:alert(1))'} onCiteClick={()=>{}}/>);
assert(!hostile.includes('<script>') && !hostile.includes('href=') && !hostile.includes('onerror='));
const code=renderToStaticMarkup(<AnswerDocument text={'\`[1, 3]\`'} onCiteClick={()=>{}}/>);
assert(code.includes('<code>[1, 3]</code>') && !code.includes('<button'));
const counts={sql:'SELECT ...',columns:['category','review_count'],rows:[['Beauty',70494],['Books',33513],['Clothing',72198]],total_rows:3};
assert.deepEqual(sqlChart(counts)?.metrics.map(x=>x.label),['Clothing','Beauty','Books']);
assert.equal(sqlChart(counts)?.kind,'comparison');
assert.equal(sqlChart({...counts,has_more:true}),null);
assert.equal(sqlChart({...counts,total_rows:20}),null);
assert.equal(sqlChart({...counts,columns:['category','revenue'],rows:[['A',null],['B',2],['C',1]]}),null);
const time={...counts,columns:['year','review_count'],rows:[[2023,4],[2021,5],[2022,2]]};
assert.deepEqual(sqlChart(time)?.metrics.map(x=>x.label),['2021','2022','2023']);
assert.equal(sqlChart(time)?.kind,'time');
assert.equal(sqlChart({...counts,columns:['date','count'],rows:[['2023-02-30',3],['2023-03-01',4],['2023-03-02',5]]}),null);
assert.equal(sqlChart({...counts,columns:['date','count'],rows:[['2021',3],['2022-01',4],['2023-01-01',5]]}),null);
const response={kind:'answer',answer:markdown,citations:[1,3].map(n=>({n,source_id:'review'+n,label:'Review',display_label:'Review',snippet:'text'})),sql:counts,thread_id:'ephemeral',user_id:'ephemeral',audit:{role:'marketing',intent:'sql',tool_path:['sql_agent'],sources:['sql'],tokens:0,cost_usd:0,latency_ms:0,scope:{restricted:false,categories:[]},grounding:{path:'calculated',issues:[]}}};
for(const role of ['marketing','executive']){
 const live=renderToStaticMarkup(<AssistantTurn res={{...response,audit:{...response.audit,role}}} state='grounded' onCiteClick={()=>{}}/>);
 const restored=renderToStaticMarkup(<AssistantTurn res={{...response,audit:{...response.audit,role}}} state='grounded' restored onCiteClick={()=>{}}/>);
 assert(live.includes('Show evidence 3') && restored.includes('Show evidence 3'));
 assert(!live.includes('Sentiment trend') && !live.includes('Ranked metric') && !live.includes('Themes'));
 assert(live.includes('Comparison of review count'));
}
const historic=renderToStaticMarkup(<AssistantTurn historical={{role:'executive',content:markdown}}/>);
assert(historic.includes('<strong>Charging</strong>') && !historic.includes('Show evidence'));
let chosen='';
const choices=QuestionSuggestions({questions:['Show five products averaging below 2 with at least 50 reviews'],onSelect:q=>{chosen=q;}});
assert(choices && choices.props.children[0].props.type === 'button');
choices.props.children[0].props.onClick();
assert.equal(chosen,'Show five products averaging below 2 with at least 50 reviews');
const conversational={...response,answer:'Your marketing role can access Electronics.',citations:[],sql:null,suggestions:['What do customers praise about Electronics?'],audit:{...response.audit,intent:'conversation',sources:[],grounding:{path:'conversation',issues:[]}}};
const conversationalState=derivePanelState({inFlight:false,response:conversational,error:null});
assert.equal(conversationalState,'grounded');
const controlHtml=renderToStaticMarkup(<AssistantTurn res={conversational} state={conversationalState} onCiteClick={()=>{}} onSuggestion={()=>{}}/>);
assert(controlHtml.includes('Your marketing role can access Electronics.') && controlHtml.includes('Suggested questions'));
assert(!controlHtml.includes("couldn’t find anything") && !controlHtml.includes('Where this came from'));
const clarifyHtml=renderToStaticMarkup(<AssistantTurn res={{...conversational,kind:'clarification',answer:'How should I select products?'}} state='no-evidence' onCiteClick={()=>{}} onSuggestion={()=>{}} restored/>);
assert(clarifyHtml.includes('How should I select products?') && clarifyHtml.includes('Suggested questions') && clarifyHtml.includes('Replayed from history'));
const noMatches={...conversational,answer:'No products matched an average below 2/5 with at least 50 reviews.',audit:{...conversational.audit,grounding:{path:'none',issues:[]}}};
const noMatchesHtml=renderToStaticMarkup(<AssistantTurn res={noMatches} state='no-evidence' onCiteClick={()=>{}} restored/>);
assert(noMatchesHtml.includes('No products matched an average below 2/5 with at least 50 reviews.'));
assert(!noMatchesHtml.includes('Try rephrasing'));
console.log('Frontend answer-quality checks passed: grouped citations, safe formatting, chart dimensions/order, partial states and replay.');
` },
  define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://test.invalid') },
  bundle: true, platform: 'node', format: 'cjs', jsx: 'automatic', write: false,
});
new Function('require','module',result.outputFiles[0].text)(require,{exports:{}});
