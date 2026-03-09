Ho bisogno che a ogni interazione venga generato un record di log che trovi in supabase nella tabella model_logs che ha il seguente schema:
- model_id
- input_tokens
- output_tokens
- user_id
- reason

model_id deve essere il modello utilizzato per la chat. C'è una apposita tabella che si chiama models col seguente schema:
- provider
- model
- input_price
- output_price

Nel log devi indicare, per ogni chat eseguita, il modello utilizzato, il numero di token di input e output, l'utente che ha eseguito la chat e il motivo per cui è stata eseguita.
Per motivo distingui tra RAG quando la chat ho implicato l'accesso al database vettoriale e CHAT quando invece la chat è avvenuta direttamente col modello.   

Fai un piano e se necessario fammi domande a cui vuoi risposta. Prima di fare sviluppi crea un branch di nome llm_logs su cui fare i commit di avanzamento. 