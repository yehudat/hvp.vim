" syntax/hvp.vim -- Synopsys HVP (HVL DSL) syntax highlighting
" LRM Reference: Synopsys HVP (HVL) DSL Language Reference

if exists('b:current_syntax')
    finish
endif

syn case match

" --- Block delimiters (Statement) ---
syn keyword hvpBlockKeyword plan endplan
syn keyword hvpBlockKeyword feature endfeature
syn keyword hvpBlockKeyword metric endmetric
syn keyword hvpBlockKeyword measure endmeasure
syn keyword hvpBlockKeyword override endoverride
syn keyword hvpBlockKeyword filter endfilter
syn keyword hvpBlockKeyword until elseuntil else enduntil
syn keyword hvpBlockKeyword subplan

" --- Declaration keywords (Type) ---
syn keyword hvpDeclKeyword attribute annotation

" --- Types (Type) ---
syn keyword hvpType integer real string percent ratio enum set aggregate

" --- Metric internals (Keyword) ---
syn keyword hvpMetricKeyword goal aggregator source

" --- Aggregators (Constant) ---
syn keyword hvpAggregator sum average min max uniquesum

" --- Filter keywords (Conditional) ---
syn keyword hvpFilterKeyword keep remove where

" --- Operators ---
syn match hvpOperator /[><!]=\?/
syn match hvpOperator /[=!]=/
syn match hvpOperator /&&/
syn match hvpOperator /||/
syn match hvpOperator /[+\-\*\/]/
syn match hvpOperator /=/

" --- Foldable regions ---
syn region hvpPlanRegion matchgroup=hvpBlockKeyword
    \ start=/\<plan\>/ end=/\<endplan\>/
    \ fold transparent
syn region hvpFeatureRegion matchgroup=hvpBlockKeyword
    \ start=/\<feature\>/ end=/\<endfeature\>/
    \ fold transparent
syn region hvpMetricRegion matchgroup=hvpBlockKeyword
    \ start=/\<metric\>/ end=/\<endmetric\>/
    \ fold transparent
syn region hvpMeasureRegion matchgroup=hvpBlockKeyword
    \ start=/\<measure\>/ end=/\<endmeasure\>/
    \ fold transparent
syn region hvpOverrideRegion matchgroup=hvpBlockKeyword
    \ start=/\<override\>/ end=/\<endoverride\>/
    \ fold transparent
syn region hvpFilterRegion matchgroup=hvpBlockKeyword
    \ start=/\<filter\>/ end=/\<endfilter\>/
    \ fold transparent
syn region hvpUntilRegion matchgroup=hvpBlockKeyword
    \ start=/\<until\>/ end=/\<enduntil\>/
    \ fold transparent

" --- Comments ---
syn keyword hvpTodo contained TODO FIXME YAGNI XXX HACK NOTE
syn match   hvpComment /\/\/.*$/ contains=hvpTodo

" --- Strings ---
syn region hvpString matchgroup=hvpStringDelim start=/"/ skip=/\\"/ end=/"/
    \ contains=hvpSourceKeyword,hvpSourceWildcard,hvpSourceBacktick,hvpSubstitution

" --- Source mini-language (inside strings) ---
syn match hvpSourceKeyword /\<\(tree\|module\|instance\|property\|group\|group bin\|group instance\|group instance bin\):/
    \ contained
syn match hvpSourceWildcard /\*\*\|\*\|?/ contained
syn match hvpSourceBacktick /`[rn\-]`/ contained
syn match hvpSubstitution  /\${[^}]\+}/ contained

" --- Literals ---
syn match hvpFloat   /\<\d\+\.\d\+\>/
syn match hvpNumber  /\<\d\+\>/
syn match hvpPercent /\<\d\+%/

" --- Hierarchy path (dotted identifiers in overrides) ---
syn match hvpHierPath /\<\w\+\(\.\w\+\)\+\>/

" --- Highlight links ---
hi def link hvpBlockKeyword   Statement
hi def link hvpDeclKeyword    Type
hi def link hvpType           Type
hi def link hvpMetricKeyword  Keyword
hi def link hvpAggregator     Constant
hi def link hvpFilterKeyword  Conditional
hi def link hvpOperator       Operator
hi def link hvpComment        Comment
hi def link hvpTodo           Todo
hi def link hvpString         String
hi def link hvpStringDelim    String
hi def link hvpNumber         Number
hi def link hvpFloat          Float
hi def link hvpPercent        Special
hi def link hvpSourceKeyword  PreProc
hi def link hvpSourceWildcard Special
hi def link hvpSourceBacktick SpecialChar
hi def link hvpSubstitution   Identifier
hi def link hvpHierPath       Identifier

let b:current_syntax = 'hvp'
