#!/usr/bin/env python3
  """                                                                           
  Downloads the compiled PDF from Overleaf by loading the project editor
  in a headless browser and intercepting the PDF network response.              
  Exit 0 = PDF updated. Exit 1 = unchanged. Exit 2 = error.                     
  """                                                                           
  import os, sys, hashlib, time                                                 
  from playwright.sync_api import sync_playwright                               
                                                                                
  SESSION    = os.environ['OVERLEAF_SESSION']
  PROJECT_ID = os.environ.get('OVERLEAF_PROJECT_ID', '63b20a7df9ce7bcb5887cb22')
  OUT_FILE   = 'resume.pdf'                                                     
   
  def sha256(path):                                                             
      if not os.path.exists(path):                          
          return None                                                           
      with open(path, 'rb') as f:                           
          return hashlib.sha256(f.read()).hexdigest()
                                                                                
  old_hash = sha256(OUT_FILE)
                                                                                
  with sync_playwright() as p:                              
      browser = p.chromium.launch(headless=True)
      context = browser.new_context(                                            
          user_agent=(
              'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '             
              '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'              
          ),
          viewport={'width': 1920, 'height': 1080},                             
      )                                                                         
      context.add_cookies([{
          'name':     'overleaf_session2',                                      
          'value':    SESSION,                                                  
          'domain':   '.overleaf.com',
          'path':     '/',                                                      
          'httpOnly': True,                                 
          'secure':   True,                                                     
          'sameSite': 'Lax',
      }])                                                                       
                                                            
      page = context.new_page()

      pdf_chunks = []                                                           
   
      def on_response(response):                                                
          if 'output.pdf' in response.url and response.status == 200:
              try:                                                              
                  body = response.body()
                  if body[:4] == b'%PDF':                                       
                      pdf_chunks.append(body)               
                      print(f'Intercepted PDF: {len(body):,} bytes')            
              except Exception as e:
                  print(f'Response body error: {e}')                            
                                                            
      page.on('response', on_response)                                          
                                                            
      print('Loading project editor…')                                          
      page.goto(
          f'https://www.overleaf.com/project/{PROJECT_ID}',                     
          wait_until='domcontentloaded',                    
          timeout=60000,                                                        
      )
                                                                                
      if '/login' in page.url:                                                  
          print('ERROR: Session cookie expired — refresh OVERLEAF_SESSION 
  secret')                                                                      
          browser.close()                                   
          sys.exit(2)                                                           
                                                            
      print(f'Editor loaded  →  {page.url}')                                    
   
      deadline = time.time() + 90                                               
      while not pdf_chunks and time.time() < deadline:      
          page.wait_for_timeout(2000)
                                                                                
      browser.close()
                                                                                
  if not pdf_chunks:                                        
      print('ERROR: PDF never loaded in editor within 90s')
      sys.exit(2)                                                               
   
  content = pdf_chunks[-1]                                                      
  new_hash = hashlib.sha256(content).hexdigest()            
  print(f'Downloaded {len(content):,} bytes  hash={new_hash[:12]}')             
                                                                                
  if old_hash == new_hash:                                                      
      print('PDF unchanged — skipping')                                         
      sys.exit(1)                                                               
                                                            
  with open(OUT_FILE, 'wb') as f:
      f.write(content)
  print('PDF updated')
