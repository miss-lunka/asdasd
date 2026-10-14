import os
import io
import re
import tempfile
import requests
import gradio as gr
from pydub import AudioSegment

DEFAULT = '«Жаттығуда бәрі істеп тұр еді ғой!»\n\nРобот сол. Код сол. Бірақ чемпионатта миссиялар орындалмай қалады. Неге?\n\nБүгін осы қатенің себебін талдаймыз.'

def analyze(text, style, pauses):
    sentences = re.findall(r'[^.!?\n]+[.!?]+|[^.!?\n]+$', text, flags=re.M)
    lines = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        emotion = 'Интрига' if '?' in sentence else ('Энергия' if '!' in sentence else 'Естественно')
        duration = 0.7 if '?' in sentence else (0.45 if pauses == 'Выразительные' else 0.25)
        lines.append(f'{sentence} | {emotion} | {duration:.2f}')
    return '\n'.join(lines)

def generate(text, reference, reference_text, speed, style, pauses, annotations):
    if not text.strip():
        raise gr.Error('Введите текст')
    if not reference:
        raise gr.Error('Загрузите запись голоса')
    url = os.getenv('VOICE_API_URL', '').strip()
    if not url:
        raise gr.Error('AI-сервер не подключен: VOICE_API_URL отсутствует')
    from gradio_client import Client, handle_file
    result = Client(url).predict(text, handle_file(reference), reference_text, api_name=os.getenv('VOICE_API_NAME', '/generate'))
    output = result[0] if isinstance(result, (tuple, list)) else result
    if isinstance(output, dict):
        output = output.get('path') or output.get('url')
    if not isinstance(output, str):
        raise gr.Error('Неожиданный ответ модели')
    if output.startswith('http'):
        response = requests.get(output, timeout=120)
        response.raise_for_status()
        sound = AudioSegment.from_file(io.BytesIO(response.content))
    else:
        sound = AudioSegment.from_file(output)
    if speed != 1:
        sound = sound._spawn(sound.raw_data, overrides={'frame_rate': int(sound.frame_rate * speed)}).set_frame_rate(sound.frame_rate)
    destination = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
    sound.export(destination, format='mp3', bitrate='192k')
    return destination, destination

with gr.Blocks(title='DAUYS — Қазақша AI дауыс') as app:
    gr.Markdown('# DAUYS\nӨз дауысыңмен қазақша мәтінді дыбыста')
    text = gr.Textbox(label='Мәтін', value=DEFAULT, lines=6)
    reference = gr.Audio(label='Образец голоса', sources=['upload', 'microphone'], type='filepath')
    reference_text = gr.Textbox(label='Расшифровка образца')
    with gr.Accordion('AI-режиссёр', open=True):
        style = gr.Dropdown(['Динамичный','Тёплый','Экспертный','Сторителлинг'], value='Динамичный', label='Стиль')
        pauses = gr.Dropdown(['Естественные','Короткие','Выразительные'], value='Естественные', label='Паузы')
        speed = gr.Slider(0.75, 1.5, value=1.1, step=0.05, label='Скорость')
        annotations = gr.Textbox(label='Эмоции и паузы', lines=5, interactive=True)
        gr.Button('Разметить текст').click(analyze, [text, style, pauses], annotations)
    output = gr.Audio(label='Аудио', type='filepath')
    download = gr.File(label='MP3')
    gr.Button('Сгенерировать MP3', variant='primary').click(generate, [text,reference,reference_text,speed,style,pauses,annotations], [output,download])
    gr.Markdown('Клонирование требует подключённого совместимого AI API. Эмоции пока не управляют синтезом.')

if __name__ == '__main__':
    app.launch()
