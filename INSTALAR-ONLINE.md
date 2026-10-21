# YouTube Playlists no Stremio — instalação online (Render)

## Passo 1: GitHub
1. Crie uma conta ou entre em https://github.com.
2. Crie um repositório novo (por exemplo, `stremio-youtube-playlists`).
3. Envie os arquivos `addon.py`, `requirements.txt` e `render.yaml` para a raiz do repositório (Add file > Upload files > Commit changes). **Não** envie o ZIP sem descompactar.

## Passo 2: Render
1. Entre em https://dashboard.render.com/.
2. Clique em New > Blueprint e conecte o repositório do GitHub.
3. O Render deve detectar `render.yaml`. Confirme a criação do serviço web gratuito, se estiver disponível.
4. Aguarde o status de deploy indicar que está ativo. Copie o domínio HTTPS gerado (por exemplo, `https://stremio-youtube-playlists-xxxx.onrender.com`).

Alternativa se o Blueprint não estiver disponível: New > Web Service; conecte o repositório; runtime Python; Build Command `pip install -r requirements.txt`; Start Command `python addon.py`; configure a variável `HOST=0.0.0.0`. Selecione plano Free, quando disponível.

## Passo 3: Instalar no Stremio
1. Abra `https://SEU-DOMINIO.onrender.com/manifest.json` no navegador. Se aparecer JSON contendo o nome do addon, o servidor respondeu.
2. Abra Stremio > Addons > Add addon; cole esse mesmo endereço do manifesto.
3. Use a busca do Stremio e cole um link de playlist pública normal do YouTube. Selecione o resultado em Série e abra os episódios.

## Limitações importantes
- A reprodução/autoavançar do player para `ytId` depende da implementação do Stremio e de restrições do YouTube: não é garantida.
- O servidor depende de `yt-dlp` para leitura de metadados. O YouTube pode bloquear ou limitar acesso a IPs de servidores em nuvem, especialmente gratuitos. Playlists privadas ou mixes automáticos podem falhar.
- Serviços gratuitos no Render hibernam após inatividade e podem demorar para reiniciar. Consulte as regras atuais antes de colocar em uso contínuo.
- Não foi efetuado um deploy real em uma conta do Render nesta entrega. Nenhum domínio público foi criado automaticamente.
