#!/usr/bin/env bash
prun() {
    poetry run "$@"
}

to_title_case() {
    echo "$@" | sed -E 's|[_ -]+| |g;s|\b.|\u&|g'
}

to_kebab_case() {
    echo "$@" | sed -E 's|[_ -]+|-|g;s|.*|\L&|g'
}

to_snake_case() {
    echo "$@" | sed -E 's|[_ -]+|_|g;s|.*|\L&|g'
}

TO_REPLACE_UNDER=template_python_library

to_replace=( "$TO_REPLACE_UNDER" "$(to_kebab_case $TO_REPLACE_UNDER)" "$(to_title_case $TO_REPLACE_UNDER)" )

read -rp 'Enter new project name: ' project_name
new_names=( "$(to_snake_case "$project_name")" "$(to_kebab_case "$project_name")" "$(to_title_case "$project_name")" )


for i in "${!to_replace[@]}"; do
    old_name="${to_replace[i]}"
    new_name="${new_names[i]}"
    echo "Renaming \"$old_name\" to \"$new_name\""

    grep -lr --exclude='project_init.sh' --exclude-dir='.git' "$old_name" . \
        | tee >(cat 1>&2) \
        | xargs -I{} sed -i 's|'"$old_name"'|'"$new_name"'|g' {}
    find . -iname '*'"$old_name"'*' \
        | tee >(cat 1>&2) \
        | sed -E 's|(.*/?)+('"$old_name"')(.*)$|\1\2\3 \1'"$new_name"'\3|' \
        | xargs -r -n2 mv $1 $2
done

grep -lr --exclude='project_init.sh' 'AUTHOR_NAME_AND_EMAIL' . \
    | xargs -I{} \
        sed -i 's|AUTHOR_NAME_AND_EMAIL|'"$(git config user.name) <$(git config user.email)>"'|g' {}

#git init
# poetry update
poetry install --sync
prun pre-commit install --install-hooks

prun pre-commit run --all-files --hook-stage manual
prun pre-commit run -a --hook-stage post-commit
