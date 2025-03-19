// Create patient.js to handle templates and note formatting

async function loadNoteTemplates() {
    try {
        const response = await fetch('/note_templates');
        if (!response.ok) {
            throw new Error('Failed to load templates');
        }
        
        const templates = await response.json();
        const selector = document.getElementById('note-template-selector');
        
        // Clear existing options except the first one
        while (selector.options.length > 1) {
            selector.options.remove(1);
        }
        
        // Group templates by category
        const templatesByCategory = {};
        
        templates.forEach(template => {
            const category = template.category || 'General';
            if (!templatesByCategory[category]) {
                templatesByCategory[category] = [];
            }
            templatesByCategory[category].push(template);
        });
        
        // Add templates to dropdown, grouped by category
        for (const category in templatesByCategory) {
            // Add optgroup for category
            const optgroup = document.createElement('optgroup');
            optgroup.label = category;
            
            // Add options for templates in this category
            templatesByCategory[category].forEach(template => {
                const option = document.createElement('option');
                option.value = template.id;
                option.textContent = template.name;
                optgroup.appendChild(option);
            });
            
            selector.appendChild(optgroup);
        }
    } catch (error) {
        console.error('Error loading templates:', error);
    }
}

async function insertTemplateContent(templateId) {
    try {
        const response = await fetch('/note_templates');
        if (!response.ok) {
            throw new Error('Failed to load templates');
        }
        
        const templates = await response.json();
        const template = templates.find(t => t.id == templateId);
        
        if (template) {
            const textarea = document.getElementById('note-text');
            textarea.value = template.content;
            textarea.focus();
        }
    } catch (error) {
        console.error('Error inserting template content:', error);
    }
}

function createNoteRow(note) {
    const row = document.createElement('tr');
    
    // Date column - handle both formats (timestamp or date)
    const dateCell = document.createElement('td');
    if (note.timestamp) {
        dateCell.textContent = note.timestamp;
    } else if (note.date) {
        dateCell.textContent = note.date;
    }

    // Add "NEW" badge if needed
    if (note.is_new) {
        const badge = document.createElement('span');
        badge.style.background = '#d1fae5';
        badge.style.color = '#047857';
        badge.style.padding = '0.2rem 0.5rem';
        badge.style.borderRadius = '4px';
        badge.style.fontSize = '0.75rem';
        badge.textContent = 'NEW';
        dateCell.appendChild(document.createTextNode(' '));
        dateCell.appendChild(badge);
    }
    
    // Staff column
    const staffCell = document.createElement('td');
    staffCell.textContent = note.staff || 'N/A';
    
    // Note column with improved formatting
    const noteCell = document.createElement('td');
    noteCell.className = 'note-cell';
    
    // Handle notes with newlines by preserving formatting but with reduced line height
    if (note.note && note.note.includes('\n')) {
        const pre = document.createElement('pre');
        pre.textContent = note.note;
        noteCell.appendChild(pre);
    } else {
        noteCell.textContent = note.note || '';
    }

    // Add to row
    row.appendChild(dateCell);
    row.appendChild(staffCell);
    row.appendChild(noteCell);
    
    return row;
}
