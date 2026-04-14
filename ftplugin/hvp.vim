" ftplugin/hvp.vim -- Synopsys HVP filetype settings

if exists('b:did_ftplugin')
    finish
endif
let b:did_ftplugin = 1

" --- Undo hook (clean up when filetype changes) ---
let b:undo_ftplugin = 'setl cms< fdm< fdn< isk< sua<'
    \ . '| unlet! b:match_words b:did_ftplugin'
    \ . '| delcommand HvpPreview'

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

" --- HVP Preview: render as markdown via glow in a terminal split ---
let s:hvp_converter = expand('<sfile>:p:h:h') . '/scripts/hvp_to_markdown.py'

function! s:HvpPreview(bang) abort
    let l:hvp_file = expand('%:p')
    if empty(l:hvp_file)
        echohl ErrorMsg | echo 'HvpPreview: buffer has no file' | echohl None
        return
    endif
    write
    let l:cmd = 'python3 "' . s:hvp_converter . '"'
        \ . ' --file "' . l:hvp_file . '"'
        \ . ' | glow -'
    " Close any existing preview buffer
    for l:buf in getbufinfo({'bufloaded': 1})
        if get(l:buf.variables, 'hvp_preview', 0)
            execute 'bwipeout!' l:buf.bufnr
        endif
    endfor
    if a:bang
        new
    else
        vnew
    endif
    setlocal buftype=nofile bufhidden=wipe noswapfile nobuflisted
    let b:hvp_preview = 1
    if has('nvim')
        call termopen(l:cmd)
    else
        execute 'terminal ++curwin' l:cmd
    endif
    setlocal nomodifiable
    wincmd p
endfunction

command! -buffer -bang HvpPreview call s:HvpPreview(<bang>0)
