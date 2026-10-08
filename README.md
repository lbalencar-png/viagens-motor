# viagens-motor

Ferramentas de planejamento de viagem para uso pessoal com o Claude: lugares, rotas, transporte público, clima, câmbio, calendário e custos. Toda resposta traz a fonte e a hora da consulta; quando a fonte falha, a ferramenta devolve o erro, nunca uma estimativa.

## Fontes e atribuição
- Mapas e lugares: © colaboradores do OpenStreetMap (https://www.openstreetmap.org/copyright); para corrigir o mapa: https://www.openstreetmap.org/fixthemap
- Geocodificação: Photon (komoot)
- Rotas: OSRM da FOSSGIS (routing.openstreetmap.de)
- Transporte público: Transitous (https://transitous.org/sources/). Uso intenso exige aviso prévio aos mantenedores do Transitous.
- Clima: Open-Meteo (https://open-meteo.com), dados sob a licença CC BY 4.0
- Câmbio: PTAX do Banco Central do Brasil e taxas de referência do BCE via Frankfurter
- Feriados: Nager.Date

## Instalação (macOS, uv)

    bash scripts/instalar.sh --config /caminho/motor-config.toml [--registrar-claude-desktop] [--agendar]

Cria o ambiente em ~/.local/share/viagens-motor/venv (Python 3.12), os comandos viagens-motor, viagens-motor-mcp e viagens-motor-saude em ~/.local/bin e, com as opções, registra o servidor no app do Claude e agenda a verificação diária (launchd, 8h35).

O verificador é o comando viagens-motor-saude: consulta cada fonte uma vez, grava status.json em ~/.local/share/viagens-motor e o resultado aparece na ferramenta saude.

## Ferramentas

lugar, rota (pe, bicicleta, carro, transporte), distancias, ordenar_dia, clima, cambio, calendario, custos, spread_da_fatura, saude. Toda resposta traz ok, fonte, consultado_em e, quando houver, aviso. Em falha, a resposta traz o erro e nenhum número.

## Configuração

Veja motor-config.exemplo.toml. IOF por meio de pagamento, spread de cada cartão e o nome da variável de ambiente da chave do Google (opcional; com ela, a Routes API entra quando a fonte aberta falha).

## Testes

    python -m pytest -q          # sem rede
    python -m pytest -q -m live  # fontes reais

Licença MIT.
