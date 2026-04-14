" plugin/preview.vim -- <Leader>P: filetype-aware preview in a vertical split
"
" Dispatches to filetype-specific preview commands when available,
" falls back to glow for markdown-like files.

if exists('g:loaded_hvp_preview')
    finish
endif
let g:loaded_hvp_preview = 1

" --- Filetype dispatch table ---
" Maps filetype -> ex command to run. Extend this dict for new formats.
let g:hvp_preview_dispatch = get(g:, 'hvp_preview_dispatch', {
    \ 'hvp': 'HvpPreview',
    \ })

" --- Generic glow preview (markdown and fallback) ---
function! s:GlowPreview(file) abort
    " Close any existing preview buffer
    for l:buf in getbufinfo({'bufloaded': 1})
        if get(l:buf.variables, 'hvp_preview', 0)
            execute 'bwipeout!' l:buf.bufnr
        endif
    endfor
    vnew
    setlocal buftype=nofile bufhidden=wipe noswapfile nobuflisted
    let l:cmd = 'glow - < ' . shellescape(a:file)
    if has('nvim')
        call termopen(l:cmd)
    else
        execute 'terminal ++curwin' l:cmd
    endif
    setlocal nonumber norelativenumber signcolumn=no nolist
    let b:hvp_preview = 1
    let b:indentLine_enabled = 0
    if exists(':IBLDisable') == 2
        IBLDisable
    endif
    setlocal nomodifiable
    wincmd p
endfunction

" --- Dispatch logic ---
function! s:PreviewDispatch() abort
    let l:file = expand('%:p')
    if empty(l:file)
        echohl ErrorMsg | echo 'Preview: buffer has no file' | echohl None
        return
    endif
    write

    let l:ft = &filetype

    " Check dispatch table for filetype-specific command
    if has_key(g:hvp_preview_dispatch, l:ft)
        execute g:hvp_preview_dispatch[l:ft]
        return
    endif

    " Markdown and friends: render with glow directly
    if l:ft ==# 'markdown' || l:ft ==# 'markdown.pandoc' || l:ft ==# 'rmd'
        call s:GlowPreview(l:file)
        return
    endif

    echohl WarningMsg
    echo 'Preview: no handler for filetype ' . l:ft
    echohl None
endfunction

nnoremap <silent> <Leader>P :call <SID>PreviewDispatch()<CR>
