// 只加载显式提供的包；全部发现根来自本次测试的临时目录。
import assert from 'node:assert/strict';
import {readFile, mkdir, readdir} from 'node:fs/promises';
import {join, dirname, resolve, relative} from 'node:path';
import {homedir} from 'node:os';
import {pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';

const [runtime, project, user, python, installer] = process.argv.slice(2);
const packageFile = name => pathToFileURL(join(runtime, 'node_modules', '@deepseek-ai', name, 'lib', 'index.js')).href;
const {FileSystemSkillProvider} = await import(packageFile('dsh-skill-filesystem'));
const {resolveDshHome} = await import(packageFile('dsh-home-paths'));
const isolated = dirname(project);
const nested = join(project, 'provider nested');
await mkdir(nested);
// 模拟 Git worktree 的文件标记，不运行或扫描真实 checkout。
const {writeFile} = await import('node:fs/promises');
await writeFile(join(project, '.git'), 'gitdir: fixture\n');
const projectRoot = join(project, '.dsh', 'skills');
const userRoot = join(user, 'skills');
const provider = new FileSystemSkillProvider(
  {get: () => undefined, logger: {warn: message => {throw Error(message);}}},
  {signal: new AbortController().signal, invalidate() {}},
  {watch: false, dshHome: user, agentsHome: join(isolated, 'agents'),
   customSkillDirs: [join(isolated, 'custom')], bundledSkillDir: join(isolated, 'bundled')}
);
const names = (await readdir(projectRoot)).sort();
assert(names.length > 0);
const list = async () => {
  const result = await provider.list({cwd: nested});
  assert(Array.isArray(result), 'Provider discovery must be complete');
  return result;
};
const uninstall = scope => {
  const result = spawnSync(python, [installer, 'uninstall', '--all', ...scope],
    {env: {...process.env, DSH_HOME: user}, encoding: 'utf8'});
  assert.equal(result.status, 0, result.stderr);
};
try {
  const roots = await provider.roots(nested);
  assert.equal(roots[0].path, projectRoot);
  const candidates = await list();
  assert.equal(candidates.length, names.length * 2);
  for (const candidate of candidates) {
    assert(names.includes(candidate.name));
    const root = candidate.source === 'project-dsh' ? projectRoot : userRoot;
    assert(['project-dsh', 'user-dsh'].includes(candidate.source));
    const directory = join(root, candidate.name);
    const loaded = await provider.get(candidate, {});
    const original = await readFile(join(directory, 'SKILL.md'), 'utf8');
    assert.equal(loaded.content, original.split('---').slice(2).join('---').trim());
    assert.equal(loaded.resourceBase.path, directory);
    const receipt = JSON.parse(await readFile(join(directory, '.forge-steward-install.json'), 'utf8'));
    // 全部资源可从客户端给出的 resourceBase 取得，摘要已由 Python 回归逐字节核对。
    for (const [resource, digest] of Object.entries(receipt.files)) {
      const path = join(loaded.resourceBase.path, resource);
      assert(!relative(directory, path).startsWith('..'));
      if (digest !== 'directory') {
        const {createHash} = await import('node:crypto');
        assert.equal(createHash('sha256').update(await readFile(path)).digest('hex'), digest);
      }
    }
  }
  // 提供方返回候选；核心目录按 rank 选胜者，此处核对提供方的优先级契约。
  for (const name of names) {
    const pair = candidates.filter(item => item.name === name).sort((a, b) => a.rank - b.rank);
    assert.equal(pair[0].source, 'project-dsh');
  }
  for (const [value, expected] of [[undefined, join(homedir(), '.dsh')], ['', join(homedir(), '.dsh')],
    ['   ', join(homedir(), '.dsh')], ['relative root', resolve('relative root')],
    [' padded ', resolve(' padded ')], ['~', homedir()], ['~/harness root', join(homedir(), 'harness root')],
    ['~\\harness root', join(homedir(), 'harness root')]]) {
    assert.equal(resolveDshHome(undefined, value === undefined ? {} : {DSH_HOME: value}), expected);
  }
  uninstall(['--project', nested]);
  const afterProject = await list();
  assert.equal(afterProject.length, names.length);
  assert(afterProject.every(item => item.source === 'user-dsh'));
  uninstall(['--user']);
  assert.deepEqual(await list(), []);
  console.log('PASS complete bodies/resources, .git file/subdirectory, home matrix, ranks and scoped removal rediscovery');
} finally {
  await provider.dispose();
}
