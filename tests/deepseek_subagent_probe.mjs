// 调用真实注册工具；只替换 provider 和结果，不复制其执行函数。
import assert from 'node:assert/strict';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
const runtime = process.argv[2];
const {apply} = await import(pathToFileURL(join(runtime, 'node_modules/@deepseek-ai/dsh-tool-subagent/lib/index.js')));
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; };
function harness(options = {}) {
  const definitions = new Map(), starts = [], results = deferred(), disposal = deferred();
  let disposed = false;
  const provider = {name:'spawn', capabilities:{depthLimit:true,agentOptions:true}, inheritsParentContext:false, prepareContinuable(){}};
  const run = {id:'fixture-child', result:results.promise, dispose(){disposed=true;return disposal.promise;}};
  const ctx = {
    tools:{register(tool){definitions.set(tool.name,tool);return () => definitions.delete(tool.name);}},
    sessionProjections:{register(){}}, on(){}, logger:{info(){}},
    systemPrompt:{section(){},getSectionOrder(){return 0;}},
    get(name){return name==='jobs' ? {start(job){starts.push(job);return 'fixture-job';}} : undefined;},
    subagents:{getProvider(){return provider;},resolveMaxDepth(){return 2;},
      async start(name,request){starts.push({name,request});return run;},
      async startContinuable(request){starts.push(request);return {childId:'fixture-background'};}}
  };
  apply(ctx, {provider:'spawn', ...options});
  const controller = new AbortController();
  const exec = {agent:{id:'parent',options:{provider:'fixture',model:'fixture'},session:{requestHeader(){}}},signal:controller.signal};
  return {tool:definitions.get('subagent'),exec,controller,starts,results,disposal,get disposed(){return disposed;}};
}
const tick = () => new Promise(resolve => setImmediate(resolve));
for (const reason of ['completed','error','aborted','max-tokens','refusal','unknown']) {
  const h = harness(); let settled=false;
  const promise=h.tool.execute({description:'fixture stage',prompt:'read-only; no push',run_in_background:false},h.exec);
  const observed=promise.then(value=>({value}),error=>({error})).finally(()=>{settled=true;});
  await tick(); assert.equal(settled,false); assert.equal(h.disposed,false); assert.equal(h.starts.length,1);
  assert.equal(h.starts[0].request.prompt[0].text,'read-only; no push');
  h.results.resolve({stopReason:reason,diagnostic:'fixture diagnostic',output:[{type:'text',text:'partial stage'}]});
  await tick(); assert.equal(h.disposed,true); assert.equal(settled,false,'foreground must await dispose');
  h.disposal.resolve(); const result=await observed;
  if(reason==='completed') {assert.equal(result.value.kind,'foreground');assert.equal(result.value.runId,'fixture-child');}
  else {assert(result.error);assert.match(result.error.message,/partial stage/);}
  assert.equal(h.starts.length,1,'no automatic re-dispatch');
}
const canceled=harness(); canceled.controller.abort('user stop');
await assert.rejects(canceled.tool.execute({description:'stop',prompt:'stop'},canceled.exec));
assert.equal(canceled.starts.length,0);
const background=harness({backgroundMode:'continuable'});
assert.deepEqual(await background.tool.execute({description:'background',prompt:'wait'},background.exec),{kind:'continuable',subagentId:'fixture-background'});
assert.equal(background.disposed,false);
assert.equal(background.tool.output.render({}, {kind:'foreground',runId:'id',output:[{type:'text',text:'done'}]})[0].text,'done');
const rejected=harness();
const promise=rejected.tool.execute({description:'broken',prompt:'read'},rejected.exec);
const observed=promise.catch(error=>error);
rejected.results.reject(Error('provider failed')); await tick(); rejected.disposal.reject(Error('dispose failed'));
assert((await observed) instanceof AggregateError); assert.equal(rejected.starts.length,1);
console.log('PASS native foreground wait/dispose, six stop reasons, cancellation, background receipt, renderer, no retry');
// provider 失去必要能力在注册阶段拒绝，不能退化为父Agent执行。
const missingTools = new Map();
const badProvider = {name:'spawn',capabilities:{depthLimit:false,agentOptions:false}};
const badContext = {tools:{register(tool){missingTools.set(tool.name,tool);}},
  subagents:{getProvider(){return badProvider;},resolveMaxDepth(){return 2;}},
  sessionProjections:{register(){}},on(){}};
assert.throws(()=>apply(badContext,{provider:'spawn'}),/cannot enforce maxDepth/);
assert.equal(missingTools.size,0);
const absentContext = {...badContext,logger:{info(){}},
  subagents:{getProvider(){return undefined;},resolveMaxDepth(){return 2;}}};
apply(absentContext,{provider:'missing',enableRunInBackground:false});
assert.equal(missingTools.size,0);
console.log('PASS missing provider and depth capability stop before tool registration');
