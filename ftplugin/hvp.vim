" ftplugin/hvp.vim -- Synopsys HVP filetype settings

if exists('b:did_ftplugin')
    finish
endif
let b:did_ftplugin = 1

" --- Undo hook (clean up when filetype changes) ---
let b:undo_ftplugin = 'setl cms< fdm< fdn< isk< sua<'
    \ . '| unlet! b:match_words b:did_ftplugin'

" --- Comment string for gc/gcc (Comment.nvim, vim-commentary) ---
setlocal commentstring=//\ %s

" --- Folding via syntax regions (defined in syntax/hvp.vim) ---
setlocal foldmethod=syntax
setlocal foldnestmax=10

" --- iskeyword: underscores are part of identifiers ---
setlocal iskeyword+=_

" --- Suffix for gf (go-to-file) ---
setlocal suffixesadd+=.hvp

" --- Matchit / vim-matchup pairs ---
if exists('loaded_matchit') || exists('g:loaded_matchup')
    let b:match_words = '\<plan\>:\<endplan\>,'
        \ . '\<feature\>:\<endfeature\>,'
        \ . '\<metric\>:\<endmetric\>,'
        \ . '\<measure\>:\<endmeasure\>,'
        \ . '\<override\>:\<endoverride\>,'
        \ . '\<filter\>:\<endfilter\>,'
        \ . '\<until\>:\<elseuntil\>:\<else\>:\<enduntil\>'
endif
