# GitHub large-file push repair

v2.18.148 prevents future G File Studio runtime/build artifacts from being added to Git.

Protected paths include:

- `workspace/runs/`
- `release/`
- `build/`
- `dist/`
- generated `g-content-analysis-report.html`
- `GFileStudio_v*_Windows_x64.zip`

## Important

`.gitignore` only prevents **future** tracking. If a large generated file is already in your local commit, remove it from the Git index and amend that commit.

Run from the repository root:

```powershell
git rm -r --cached --ignore-unmatch workspace/runs
git rm -r --cached --ignore-unmatch release
git rm -r --cached --ignore-unmatch build
git rm -r --cached --ignore-unmatch dist
git add .gitignore
git add .
git status
git commit --amend --no-edit
git push origin master
```

These `git rm --cached` commands remove files only from Git tracking; they do **not** delete the local working files.

If the large file exists in more than the latest local commit, use `git filter-repo` to rewrite the affected local history before pushing:

```powershell
python -m pip install git-filter-repo
git filter-repo --path workspace/runs --path release --path build --path dist --invert-paths
```

After `git filter-repo`, verify `git remote -v`; if `origin` was removed, add it again and push the cleaned history only after reviewing it.
