#!/usr/bin/env bash
# C5.2 probe: does src/test/publicData.test.ts really read app/public/data/meta.json?
# Usage: public_data_probe.sh <app-COPY with node_modules>   (never the real app/)
# Each case rewrites public/data/meta.json (or studyContent.ts), runs the relevant tests, restores.
set -u
A="$1"; cd "$A" || exit 2
F=public/data/meta.json; cp "$F" "$F.bak"; S=src/lib/studyContent.ts; cp "$S" "$S.bak"
run() { npx vitest run "$2" --reporter=dot > .probe.out 2>&1; rc=$?; echo "$1 -> rc=$rc $(grep -oE 'Tests +[^(]+\([0-9]+\)' .probe.out | head -1)"; cp "$F.bak" "$F"; cp "$S.bak" "$S"; }
py() { python3 -c "import json,sys;d=json.load(open('$F'));$1;open('$F','w').write(json.dumps(d,indent=2))"; }
run "baseline" src/test/publicData.test.ts
py "d['schema_version']='0.2.0'"; run "schema_version 0.2.0" src/test/publicData.test.ts
py "d['extra']=1"; run "extra envelope key" src/test/publicData.test.ts
py "d['generated_at']=d['generated_at'].replace('Z','+00:00')"; run "generated_at +00:00" src/test/publicData.test.ts
py "d['data']['milestone']='0'"; run "milestone as string" src/test/publicData.test.ts
printf '{"x": NaN}' > "$F"; run "bare NaN token" src/test/publicData.test.ts
rm "$F"; run "meta.json deleted" src/test/publicData.test.ts
py "d['data']['data_sources'][0]['licence']='CC BY 4.0'"; run "py data_sources licence wrong (full suite)" ""
py "d['data']['data_sources']=[]"; run "py data_sources emptied (full suite)" ""
sed -i "0,/licence: 'CC BY-SA 4.0'/s//licence: 'CC BY 4.0'/" "$S"; run "app DATA_SOURCES[0] licence wrong (full suite)" ""
rm -f "$F.bak" "$S.bak" .probe.out
